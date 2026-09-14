from pubsub.ingestion import ingest_transaction
from investigations.service import process_queue_item
from validation.reliability.test_idempotency import _event
import audit
import json


def test_report_records_prompt_and_hashes(isolated_db):
    ingest_transaction(_event(txn_id="T-PROV", source_event_id="EVT-PROV"), message_id="m-p")
    processed = process_queue_item(txn_id="T-PROV")
    report = processed["report"]
    assert report["prompt_version"]
    assert report["evidence_hash"]
    events = audit.list_for_case("T-PROV")
    prov = [e for e in events if e["event_type"] == "model_provenance"]
    assert prov
    detail = json.loads(prov[-1]["detail"])
    assert detail.get("prompt_version")
