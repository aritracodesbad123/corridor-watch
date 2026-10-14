import transcript from "../../data/vo-transcript.json";
import scenes from "../../data/scenes.json";

export const VO_DURATION_S = transcript.duration_s;
export const MASTER_DURATION_S = scenes.master_duration_s as number;
export const VO_WORDS = transcript.words;
export const SCENES = scenes.scenes;

export function secToFrame(sec: number, fps = 30): number {
  return Math.round(sec * fps);
}

export function frameToSec(frame: number, fps = 30): number {
  return frame / fps;
}

/** First word whose start >= t (seconds). */
export function wordAt(t: number): (typeof VO_WORDS)[number] | null {
  for (let i = VO_WORDS.length - 1; i >= 0; i--) {
    if (VO_WORDS[i].start <= t) return VO_WORDS[i];
  }
  return null;
}

export function sceneAt(t: number) {
  for (const s of SCENES) {
    const end = (s as { picture_end?: number }).picture_end ?? s.vo_end;
    if (t >= s.vo_start && t < end) return s;
  }
  return SCENES[SCENES.length - 1];
}
