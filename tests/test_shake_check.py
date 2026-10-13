"""Day-2 shake gate: still holds pass; circular crop-shake fails."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def _write_video(path: Path, frames: list[np.ndarray], fps: float = 30.0) -> None:
    h, w = frames[0].shape[:2]
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for f in frames:
        vw.write(f)
    vw.release()


def test_shake_check_passes_still_and_fails_orbit(tmp_path):
    rng = np.random.default_rng(1)
    base = rng.integers(0, 255, (180, 320, 3), dtype=np.uint8)
    cv2.rectangle(base, (40, 30), (220, 140), (200, 160, 40), -1)

    still = tmp_path / "still.mp4"
    _write_video(still, [base.copy() for _ in range(60)])

    shake = tmp_path / "shake.mp4"
    frames = []
    for i in range(60):
        dx = 2.5 * np.sin(i / 5)
        dy = 2.5 * np.cos(i / 4)
        m = np.float32([[1, 0, dx], [0, 1, dy]])
        frames.append(cv2.warpAffine(base, m, (320, 180), borderMode=cv2.BORDER_REFLECT))
    _write_video(shake, frames)

    holds = tmp_path / "holds.json"
    holds.write_text('{"holds":[{"scene":"T","label":"h","start_s":0.3,"end_s":1.5}]}')

    py = ROOT / ".venv" / "bin" / "python"
    exe = str(py) if py.is_file() else sys.executable
    script = ROOT / "scripts" / "shake_check.py"

    ok = subprocess.run([exe, str(script), str(still), "--holds", str(holds)], cwd=ROOT)
    assert ok.returncode == 0

    bad = subprocess.run([exe, str(script), str(shake), "--holds", str(holds)], cwd=ROOT)
    assert bad.returncode == 1
