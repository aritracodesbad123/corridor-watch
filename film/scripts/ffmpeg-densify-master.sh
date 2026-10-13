#!/usr/bin/env bash
# Day-2: densify crop-shake DISABLED — sin/cos crop was the circular screen shake.
# This script is now a no-op copy so old render chains don't reintroduce shake.
set -euo pipefail
cd "$(dirname "$0")/.."
SRC="${1:-out/corridor-watch-1080p.mp4}"
LOG=out/logs/ffmpeg-densify.log
mkdir -p out/logs
echo "=== densify DISABLED $(date -u) === src=$SRC (no crop-shake)" | tee "$LOG"
if [ ! -f "$SRC" ]; then
  echo "missing $SRC" | tee -a "$LOG"
  exit 1
fi
# Prefer clean pre-densify master if present
if [ -f out/corridor-watch-1080p.pre-densify.mp4 ]; then
  cp -f out/corridor-watch-1080p.pre-densify.mp4 out/corridor-watch-1080p.mp4
  echo "restored pre-densify master" | tee -a "$LOG"
else
  cp -f "$SRC" out/corridor-watch-1080p.pre-densify.mp4
  echo "backed up current as pre-densify (unchanged encode)" | tee -a "$LOG"
fi
cp -f out/corridor-watch-1080p.mp4 out/corridor-watch-master.mp4
echo DENSIFY_SKIPPED_NO_SHAKE | tee -a "$LOG"
