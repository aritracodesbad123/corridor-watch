import { Easing, interpolate } from "remotion";

export const enter = Easing.bezier(0.22, 1, 0.36, 1);
export const exit = Easing.bezier(0.64, 0, 0.78, 0);
export const move = Easing.bezier(0.65, 0, 0.35, 1);

export function fadeUp(
  frame: number,
  start: number,
  dur = 24,
): { opacity: number; y: number; blur: number } {
  const t = interpolate(frame, [start, start + dur], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });
  return {
    opacity: t,
    y: (1 - t) * 16,
    blur: (1 - t) * 8,
  };
}

export function holdBreath(_frame: number, _period = 180): number {
  // Day-2: no ambient pulse during holds (was a continuous sin sway).
  return 0;
}
