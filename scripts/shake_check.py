#!/usr/bin/env python3
"""Hold-segment shake gate: cv2.phaseCorrelate shift must be ≤0.3px between consecutive frames.

Reads hold windows from film/data/shake_holds.json (absolute seconds on the master).
Prints a per-scene report. Exit 1 if any hold exceeds the threshold.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HOLDS = ROOT / "film" / "data" / "shake_holds.json"
MAX_SHIFT_PX = 0.3


def load_holds(path: Path) -> list[dict]:
    data = json.loads(path.read_text())
    return list(data.get("holds") or [])


def frame_shift(a: np.ndarray, b: np.ndarray) -> float:
    """Global translation magnitude via phase correlation (px)."""
    ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).astype(np.float32)
    # Hann window reduces edge artifacts
    h, w = ga.shape
    win = cv2.createHanningWindow((w, h), cv2.CV_32F)
    (dx, dy), _ = cv2.phaseCorrelate(ga * win, gb * win)
    return float(np.hypot(dx, dy))


def check_hold(cap: cv2.VideoCapture, fps: float, start_s: float, end_s: float) -> dict:
    start_f = int(round(start_s * fps))
    end_f = int(round(end_s * fps))
    if end_f <= start_f + 1:
        return {"max_shift_px": 0.0, "pairs": 0, "fail_at": None}

    max_shift = 0.0
    fail_at = None
    prev = None
    for f in range(start_f, end_f + 1):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, frame = cap.read()
        if not ok:
            break
        if prev is not None:
            shift = frame_shift(prev, frame)
            if shift > max_shift:
                max_shift = shift
            if shift > MAX_SHIFT_PX and fail_at is None:
                fail_at = f / fps
        prev = frame
    return {"max_shift_px": max_shift, "pairs": max(0, end_f - start_f), "fail_at": fail_at}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("video", type=Path, help="Master mp4 path")
    ap.add_argument("--holds", type=Path, default=DEFAULT_HOLDS)
    ap.add_argument("--max-px", type=float, default=MAX_SHIFT_PX)
    args = ap.parse_args()

    if not args.video.is_file():
        print(f"FAIL missing video: {args.video}", file=sys.stderr)
        return 1
    if not args.holds.is_file():
        print(f"FAIL missing holds: {args.holds}", file=sys.stderr)
        return 1

    holds = load_holds(args.holds)
    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        print(f"FAIL cannot open {args.video}", file=sys.stderr)
        return 1
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0) or 30.0

    print(f"shake_check video={args.video} fps={fps:.3f} holds={len(holds)} max_px={args.max_px}")
    print(f"{'scene':<8} {'label':<28} {'start':>7} {'end':>7} {'max_px':>8} {'status'}")
    failed = 0
    by_scene: dict[str, list[float]] = {}
    for h in holds:
        scene = str(h.get("scene") or "?")
        label = str(h.get("label") or "hold")
        start_s = float(h["start_s"])
        end_s = float(h["end_s"])
        result = check_hold(cap, fps, start_s, end_s)
        mx = result["max_shift_px"]
        ok = mx <= args.max_px
        status = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        by_scene.setdefault(scene, []).append(mx)
        print(
            f"{scene:<8} {label:<28} {start_s:7.2f} {end_s:7.2f} {mx:8.3f} {status}"
            + (f"  first_fail@{result['fail_at']:.2f}s" if result["fail_at"] is not None else "")
        )

    cap.release()
    print("--- per-scene max ---")
    for scene, vals in sorted(by_scene.items()):
        print(f"{scene}: max={max(vals):.3f}px n={len(vals)}")

    if failed:
        print(f"FAIL {failed} hold(s) exceeded {args.max_px}px")
        return 1
    print("PASS all holds ≤ {:.2f}px".format(args.max_px))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
