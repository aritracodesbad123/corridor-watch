"""Deterministic evaluation harness for the synthetic benchmark.

The benchmark uses the generator's fraud_scenario labels as ground truth. It is
intentionally independent of Gemini so model availability cannot inflate the
core detection metrics. The output is suitable for a demo scorecard and CI.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from db import connect, init_schema
from investigation_dag import run_dag
from validation.oracle import extract, is_positive, label_of

POSITIVE_SCENARIOS = {
    "mule_pass_through",
    "split_transaction_laundering",
    "shared_device_ring",
    "synthetic_identity",
    "multi_hop_chain",
}


def _binary_metrics(y_true: list[bool], y_pred: list[bool]) -> dict[str, float | int]:
    tp = sum(a and b for a, b in zip(y_true, y_pred))
    fp = sum((not a) and b for a, b in zip(y_true, y_pred))
    fn = sum(a and (not b) for a, b in zip(y_true, y_pred))
    tn = sum((not a) and (not b) for a, b in zip(y_true, y_pred))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "false_positive_rate": round(fp / (fp + tn), 4) if fp + tn else 0.0,
    }


@contextmanager
def _clean_synthetic_db() -> Iterator[None]:
    """Score the generator cut, not the mixed demo ledger."""
    import db
    import data_gen

    old_db = db.DB_PATH
    old_gen = data_gen.DB_PATH
    tmpdir = Path(tempfile.mkdtemp(prefix="cw-eval-"))
    tmp = tmpdir / "synthetic_v1.db"
    db.DB_PATH = tmp
    data_gen.DB_PATH = tmp
    data_gen.DEVICES.clear()
    data_gen.BENEFICIARIES.clear()
    data_gen.ACCOUNT_DEVICES.clear()
    data_gen.ACCOUNT_BENEFS.clear()
    data_gen.SESSIONS.clear()
    data_gen.random.seed(42)
    data_gen.Faker.seed(42)
    try:
        accounts, txns = data_gen.build()
        data_gen.write_db(accounts, txns)
        from graph_features import score_all, write_scores
        con = connect()
        scores, _, _ = score_all(con)
        write_scores(con, scores, txns)
        con.close()
        yield
    finally:
        db.DB_PATH = old_db
        data_gen.DB_PATH = old_gen
        shutil.rmtree(tmpdir, ignore_errors=True)


@contextmanager
def _dist_b_db() -> Iterator[None]:
    """Score generator B, not data_gen."""
    import db
    from validation.external import generator_b

    old_db = db.DB_PATH
    tmpdir = Path(tempfile.mkdtemp(prefix="cw-eval-b-"))
    tmp = tmpdir / "dist_b.db"
    db.DB_PATH = tmp
    try:
        accounts, txns = generator_b.build()
        generator_b.write_db(accounts, txns)
        from graph_features import score_all, write_scores
        con = connect()
        scores, _, _ = score_all(con)
        write_scores(con, scores, txns)
        con.close()
        yield
    finally:
        db.DB_PATH = old_db
        shutil.rmtree(tmpdir, ignore_errors=True)


def run_evaluation(include_trace: bool = False, cut: str = "clean", positive: set[str] | None = None) -> dict[str, Any]:
    if cut == "clean":
        with _clean_synthetic_db():
            return run_evaluation(include_trace=include_trace, cut="ledger")
    if cut == "dist_b":
        from validation.external.generator_b import POSITIVE_B
        with _dist_b_db():
            return run_evaluation(include_trace=include_trace, cut="ledger_b", positive=POSITIVE_B)
    init_schema()
    con = connect()
    rows = [dict(r) for r in con.execute(
        "SELECT * FROM transactions ORDER BY txn_id"
    ).fetchall()]
    con.close()

    if not rows:
        return {"status": "no_data", "message": "Generate the synthetic dataset first."}

    positive = positive or POSITIVE_SCENARIOS
    labels = extract(rows, positive)
    y_true: list[bool] = []
    y_pred: list[bool] = []
    by_scenario: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "flagged": 0})
    pattern_confusion: Counter[tuple[str, str]] = Counter()
    positive_total = 0
    pattern_correct = 0
    examples = []

    # Core benchmark is based on the deterministic graph/rule detector.
    for txn in rows:
        bundle = run_dag(txn["txn_id"], audit_events=False)
        verdict = bundle["verdict"]
        truth = is_positive(txn["txn_id"], labels)
        predicted = float(verdict.get("risk_score", 0)) >= 40
        y_true.append(truth)
        y_pred.append(predicted)
        scenario = label_of(txn["txn_id"], labels)
        predicted_pattern = verdict.get("primary_pattern")
        if truth:
            positive_total += 1
            pattern_correct += int(predicted_pattern == scenario)
            pattern_confusion[(scenario, predicted_pattern)] += 1
        by_scenario[scenario]["total"] += 1
        by_scenario[scenario]["flagged"] += int(predicted)
        if include_trace and len(examples) < 20:
            examples.append({
                "txn_id": txn["txn_id"],
                "truth": scenario,
                "predicted_risk": verdict.get("risk_score"),
                "predicted_pattern": verdict.get("primary_pattern"),
            })

    metrics = _binary_metrics(y_true, y_pred)
    per_scenario = {}
    for scenario, stats in sorted(by_scenario.items()):
        per_scenario[scenario] = {
            **stats,
            "flag_rate": round(stats["flagged"] / stats["total"], 4) if stats["total"] else 0.0,
        }

    result = {
        "status": "ok",
        "benchmark": "dist_b" if cut == "ledger_b" else "synthetic_v1",
        "ground_truth": "validation.oracle (eval-only; runtime ignores fraud_scenario)",
        "positive_scenarios": sorted(positive),
        "sample_count": len(rows),
        "metrics": metrics,
        "per_scenario": per_scenario,
        "pattern_accuracy": round(pattern_correct / positive_total, 4) if positive_total else 0.0,
        "pattern_confusion": {f"{truth}->{pred}": n for (truth, pred), n in sorted(pattern_confusion.items())},
        "quality_gate": {
            "minimum_recall": 0.90,
            "minimum_precision": 0.50,
            "minimum_pattern_accuracy": 0.90,
            "passed": (metrics["recall"] >= 0.90 and metrics["precision"] >= 0.50
                       and (pattern_correct / positive_total if positive_total else 0.0) >= 0.90),
        },
    }
    if include_trace:
        result["examples"] = examples
    result["baseline_comparison"] = compare_to_transaction_baseline(rows, positive=positive)
    result["impact"] = impact_metrics(result, result["baseline_comparison"])
    if cut != "ledger_b":
        result["network_metrics"] = _network_eval(rows, labels)
    return result


def _network_eval(rows: list[dict], labels: dict[str, dict]) -> dict[str, Any]:
    from graph.investigator import bounded_network
    from graph.network_metrics import score_network

    by_label: dict[str, list[dict]] = defaultdict(list)
    for txn in rows:
        lab = label_of(txn["txn_id"], labels)
        if is_positive(txn["txn_id"], labels):
            by_label[lab].append(txn)
    scored = []
    for lab, cluster in by_label.items():
        truth_nodes = {t["sender_id"] for t in cluster} | {t["receiver_id"] for t in cluster}
        truth_edges = [(t["sender_id"], t["receiver_id"]) for t in cluster]
        seed = cluster[0]
        pred = bounded_network(seed)
        scored.append({"label": lab, **score_network(pred, {"nodes": truth_nodes, "edges": truth_edges, "key_nodes": truth_nodes})})
    if not scored:
        return {"status": "no_positive_clusters"}
    rec = sum(s["account_recall"]["recall"] for s in scored) / len(scored)
    return {
        "clusters": len(scored),
        "account_recall": round(rec, 4),
        "key_node_recall": round(sum(s["key_node_recall"]["recall"] for s in scored) / len(scored), 4),
        "relationship_reconstruction": round(sum(s["relationship_reconstruction"]["recall"] for s in scored) / len(scored), 4),
        "path_recovery": round(sum(s["path_recovery"]["recall"] for s in scored) / len(scored), 4),
        "per_cluster": scored,
    }


def transaction_only_predict(txn: dict) -> bool:
    """Deliberately simple thresholds. No graph, DNA, or Gemini."""
    amount = float(txn.get("amount") or 0)
    age = txn.get("account_age_days")
    try:
        age_n = float(age) if age is not None else None
    except (TypeError, ValueError):
        age_n = None
    try:
        velocity = int(txn.get("sender_velocity") or 0)
    except (TypeError, ValueError):
        velocity = 0
    if amount >= 8000:
        return True
    if age_n is not None and age_n <= 3 and amount >= 2500:
        return True
    if velocity >= 4 and amount >= 2000:
        return True
    return False


def compare_to_transaction_baseline(rows: list[dict] | None = None, positive: set[str] | None = None) -> dict[str, Any]:
    init_schema()
    con = connect()
    if rows is None:
        rows = [dict(r) for r in con.execute("SELECT * FROM transactions ORDER BY txn_id").fetchall()]
    ages = {}
    try:
        ages = {
            r["account_id"]: r["account_age_days"]
            for r in con.execute("SELECT account_id, account_age_days FROM risk_scores").fetchall()
        }
    except Exception:
        ages = {}
    con.close()
    sender_counts = Counter(t.get("sender_id") for t in rows)
    enriched = []
    for txn in rows:
        item = dict(txn)
        if item.get("account_age_days") is None:
            item["account_age_days"] = ages.get(item.get("sender_id"))
        item["sender_velocity"] = sender_counts.get(item.get("sender_id")) or 0
        enriched.append(item)
    labels = extract(enriched, positive or POSITIVE_SCENARIOS)
    y_true = [is_positive(txn["txn_id"], labels) for txn in enriched]
    y_base = [transaction_only_predict(txn) for txn in enriched]
    return {
        "name": "transaction_only",
        "rules": [
            "amount >= 8000",
            "account_age_days <= 3 and amount >= 2500",
            "sender_velocity >= 4 and amount >= 2000",
        ],
        "metrics": _binary_metrics(y_true, y_base),
        "network_detection": None,
        "note": "Threshold-only baseline. No graph, Pattern DNA, or Gemini.",
    }


def _parse_ts(value: str | None):
    if not value:
        return None
    raw = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _ledger_impact() -> dict[str, Any]:
    init_schema()
    con = connect()
    coverage = None
    actionability = None
    time_to_case = None
    try:
        cases = int(con.execute("SELECT COUNT(*) AS c FROM investigations").fetchone()["c"])
        evidenced = int(con.execute(
            "SELECT COUNT(*) AS c FROM investigations WHERE ai_summary IS NOT NULL AND ai_summary != ''"
        ).fetchone()["c"])
        if cases:
            coverage = round(evidenced / cases, 4)
        actionable = int(con.execute(
            """SELECT COUNT(*) AS c FROM investigations
               WHERE risk_level IN ('hold_payment','escalate_fiu','freeze_account','monitor')"""
        ).fetchone()["c"])
        if cases:
            actionability = round(actionable / cases, 4)
        rows = con.execute(
            """SELECT created_at, completed_at FROM investigation_queue
               WHERE status='COMPLETED' AND completed_at IS NOT NULL"""
        ).fetchall()
        deltas = []
        for row in rows:
            start = _parse_ts(row["created_at"])
            end = _parse_ts(row["completed_at"])
            if start and end:
                deltas.append(max(0.0, (end - start).total_seconds()))
        if deltas:
            time_to_case = round(sum(deltas) / len(deltas), 2)
    except Exception:
        pass
    con.close()
    return {
        "evidence_coverage": coverage,
        "analyst_actionability_rate": actionability,
        "time_to_case_ready": time_to_case,
    }


def impact_metrics(detection: dict, baseline: dict) -> dict[str, Any]:
    from graph.corridor import investigation_compression

    cw = (detection or {}).get("metrics") or {}
    base = (baseline or {}).get("metrics") or {}
    compression = investigation_compression()
    fp_reduction = None
    if base.get("false_positive_rate") is not None and cw.get("false_positive_rate") is not None:
        fp_reduction = round(float(base["false_positive_rate"]) - float(cw["false_positive_rate"]), 4)
    recall_lift = None
    if base.get("recall") is not None and cw.get("recall") is not None:
        recall_lift = round(float(cw["recall"]) - float(base["recall"]), 4)
    ledger = _ledger_impact()
    return {
        "investigation_compression": compression,
        "false_positive_reduction": fp_reduction,
        "network_detection_lift": recall_lift,
        "evidence_coverage": ledger["evidence_coverage"],
        "analyst_actionability_rate": ledger["analyst_actionability_rate"],
        "time_to_case_ready": ledger["time_to_case_ready"],
        "note": "Compression and lift are measured on the synthetic ledger, not production banks.",
    }


def persist_benchmark(kind: str, payload: dict) -> None:
    from db import connect, init_schema, upsert
    from pubsub.schemas import utc_now

    init_schema()
    con = connect()
    upsert(con, "platform_benchmarks", "benchmark_id", {
        "benchmark_id": f"{kind}-latest",
        "created_at": utc_now(),
        "kind": kind,
        "payload": json.dumps(payload),
    })
    con.commit()
    con.close()


def load_benchmark(kind: str) -> dict | None:
    init_schema()
    con = connect()
    try:
        row = con.execute(
            "SELECT payload, created_at FROM platform_benchmarks WHERE benchmark_id=?",
            (f"{kind}-latest",),
        ).fetchone()
    except Exception:
        row = None
    con.close()
    if not row:
        return None
    try:
        data = json.loads(row["payload"])
    except (TypeError, json.JSONDecodeError):
        return None
    data["recorded_at"] = row["created_at"]
    return data


def scorecard() -> dict:
    from graph.corridor import investigation_compression
    from pathlib import Path

    detection = load_benchmark("detection")
    ingest = load_benchmark("ingest")
    baseline = load_benchmark("baseline")
    compression = load_benchmark("compression") or investigation_compression()
    file_path = Path(__file__).resolve().parent / "benchmarks" / "latest.json"
    file_payload = None
    if file_path.exists():
        try:
            file_payload = json.loads(file_path.read_text())
        except json.JSONDecodeError:
            file_payload = None
    if file_payload:
        detection = detection or file_payload.get("detection")
        ingest = ingest or file_payload.get("ingest")
        compression = file_payload.get("investigation_compression") or compression
    decisions = {"clear": 0, "confirmed": 0, "total": 0}
    con = connect()
    try:
        rows = con.execute("SELECT decision, COUNT(*) AS c FROM analyst_decisions GROUP BY decision").fetchall()
        for r in rows:
            n = int(r["c"])
            decisions["total"] += n
            if r["decision"] == "clear":
                decisions["clear"] += n
            if r["decision"] in {"hold_payment", "escalate_fiu", "freeze_account"}:
                decisions["confirmed"] += n
    except Exception:
        pass
    con.close()
    fp_rate = None
    if decisions["total"]:
        fp_rate = round(decisions["clear"] / decisions["total"], 4)
    metrics = (detection or {}).get("metrics") or {}
    return {
        "detection": detection,
        "ingest": ingest,
        "investigation_compression": compression,
        "false_positives": {
            "benchmark_fp": metrics.get("fp"),
            "benchmark_false_positive_rate": metrics.get("false_positive_rate"),
            "analyst_clear_rate": fp_rate,
            "analyst_decisions": decisions,
            "note": "Oracle label (generator/eval-only) ≠ analyst disposition ≠ confirmed-fraud ≠ regulatory finding.",
        },
        "source": "measured",
        "baseline_comparison": baseline or (detection or {}).get("baseline_comparison"),
        "impact": (detection or {}).get("impact") or {
            "investigation_compression": compression,
            "false_positive_reduction": None,
            "network_detection_lift": None,
            "evidence_coverage": None,
            "analyst_actionability_rate": None,
            "time_to_case_ready": None,
        },
    }


def benchmark_summary() -> str:
    result = run_evaluation()
    return json.dumps(result, indent=2)
