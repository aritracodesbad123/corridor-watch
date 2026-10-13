import { useCurrentFrame, useVideoConfig } from "remotion";

/** Seconds within the current scene sequence (frame 0 = scene start). */
export function useLocalSec(): number {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return frame / fps;
}

export function sec(frameOrSec: number, fps: number): number {
  return frameOrSec; // alias for clarity in second-based keyframes
}

export function fade(
  t: number,
  inStart: number,
  inEnd: number,
  outStart?: number,
  outEnd?: number,
): number {
  let o = 0;
  if (t >= inStart) o = Math.min(1, (t - inStart) / Math.max(0.001, inEnd - inStart));
  if (outStart != null && outEnd != null && t >= outStart) {
    o *= Math.max(0, 1 - (t - outStart) / Math.max(0.001, outEnd - outStart));
  }
  return Math.max(0, Math.min(1, o));
}
