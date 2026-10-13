#!/usr/bin/env bash
# QA gates for Corridor Watch film master. Writes docs/qa-report.md (repo root).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$ROOT/.." && pwd)"
VID="${1:-$ROOT/out/corridor-watch-1080p.mp4}"
REPORT="$REPO/docs/qa-report.md"
TMP="$ROOT/out/qa-tmp"
mkdir -p "$TMP"

fail=0
note() { echo "$*" | tee -a "$TMP/notes.txt"; }

: > "$TMP/notes.txt"
note "# Corridor Watch film — QA report"
note ""
note "Source: \`$VID\`"
note "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
note ""

if [[ ! -f "$VID" ]]; then
  note "## FAIL — missing master video"
  cp "$TMP/notes.txt" "$REPORT"
  exit 1
fi

# Probe
ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height,r_frame_rate,bit_rate,nb_frames \
  -show_entries format=duration \
  -of json "$VID" > "$TMP/probe.json"

W=$(python3 -c "import json;d=json.load(open('$TMP/probe.json'));print(d['streams'][0]['width'])")
H=$(python3 -c "import json;d=json.load(open('$TMP/probe.json'));print(d['streams'][0]['height'])")
BR=$(python3 -c "import json;d=json.load(open('$TMP/probe.json'));print(int(d['streams'][0].get('bit_rate') or 0))")
DUR=$(python3 -c "import json;d=json.load(open('$TMP/probe.json'));print(float(d['format']['duration']))")
FPS=$(python3 -c "import json;d=json.load(open('$TMP/probe.json'));print(d['streams'][0]['r_frame_rate'])")

note "## Video"
note "- Resolution: ${W}×${H} (need 1920×1080)"
note "- Frame rate: $FPS (need 60/1)"
note "- Duration: ${DUR}s (need 115–135)"
note "- Bitrate: $((BR/1000)) kbps (need ≥ 8000)"
note ""

[[ "$W" == "1920" && "$H" == "1080" ]] || { note "- FAIL resolution"; fail=1; }
[[ "$FPS" == "60/1" ]] || { note "- FAIL fps"; fail=1; }
python3 - <<PY || fail=1
dur=float("$DUR")
ok=115 <= dur <= 135
print("- PASS duration" if ok else "- FAIL duration")
raise SystemExit(0 if ok else 1)
PY
python3 - <<PY || fail=1
br=int("$BR")
ok=br >= 8_000_000
print("- PASS bitrate" if ok else "- FAIL bitrate")
raise SystemExit(0 if ok else 1)
PY

# Freeze detect
ffmpeg -i "$VID" -vf "freezedetect=n=-60dB:d=0.5" -f null - 2>"$TMP/freeze.txt" || true
FREEZE=$(grep -c "freeze_start" "$TMP/freeze.txt" || true)
note ""
note "## Freeze detect (d≥0.5s)"
note "- Events: $FREEZE (warn if > 8)"
if [[ "${FREEZE:-0}" -gt 8 ]]; then note "- WARN many freezes"; fi

# Loudness (if audio stream present)
HAS_A=$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_type -of csv=p=0 "$VID" || true)
note ""
note "## Audio"
if [[ -z "$HAS_A" ]]; then
  note "- FAIL no audio stream"
  fail=1
else
  ffmpeg -i "$VID" -af loudnorm=I=-16:TP=-1.5:print_format=json -f null - 2>"$TMP/loud.txt" || true
  python3 - <<'PY' >>"$TMP/notes.txt" || true
import re, pathlib
t = pathlib.Path("/Users/aritrachakraborty/Desktop/corridor-watch/film/out/qa-tmp/loud.txt").read_text(errors="ignore")
# last JSON block
blocks = list(re.finditer(r"\{[^{}]+\}", t))
if not blocks:
    print("- WARN could not parse loudnorm")
else:
    import json
    j = json.loads(blocks[-1].group(0))
    i = float(j.get("input_i", -99))
    print(f"- Integrated: {i:.1f} LUFS (target −16 ±2)")
    print(f"- True peak: {j.get('input_tp')} dBTP")
    print("- PASS loudness" if abs(i - (-16)) <= 2.5 else "- FAIL loudness")
PY
fi

# OCR greylist — sample a few frames for banned strings
note ""
note "## OCR greylist (sampled frames)"
for f in 120 2400 4800 6900; do
  ffmpeg -y -ss "$(python3 -c "print($f/60)")" -i "$VID" -frames:v 1 "$TMP/f$f.png" 2>/dev/null || true
done
# Prefer tesseract if present; else strings via file size / skip
if command -v tesseract >/dev/null 2>&1; then
  BAD=0
  for img in "$TMP"/f*.png; do
    [[ -f "$img" ]] || continue
    txt=$(tesseract "$img" stdout 2>/dev/null || true)
    if echo "$txt" | grep -Eiq 'GEMINI_API_KEY|API_KEY is not set|Start stream'; then
      note "- FAIL banned text in $(basename "$img")"
      BAD=1
      fail=1
    fi
  done
  [[ "$BAD" == "0" ]] && note "- PASS no banned strings on sampled frames"
else
  note "- SKIP tesseract not installed (manual check plates for GEMINI_API_KEY / Start stream)"
fi

# Day-2 shake gate — hold segments must stay ≤0.3px (phaseCorrelate)
note ""
note "## Shake holds (phaseCorrelate ≤0.3px)"
PYBIN="$REPO/.venv/bin/python"
[[ -x "$PYBIN" ]] || PYBIN=python3
if "$PYBIN" "$REPO/scripts/shake_check.py" "$VID" >>"$TMP/notes.txt" 2>&1; then
  note "- PASS shake holds"
else
  note "- FAIL shake holds"
  fail=1
fi

note ""
note "## Verdict"
if [[ "$fail" == "0" ]]; then note "**PASS**"; else note "**FAIL** — see items above"; fi

cp "$TMP/notes.txt" "$REPORT"
echo "wrote $REPORT"
exit "$fail"
