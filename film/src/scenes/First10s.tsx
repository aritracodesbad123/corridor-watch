import React from "react";
import { AbsoluteFill, Audio, Sequence, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { S00_Hook } from "./S00_Hook";
import { colors, safe } from "../design/tokens";
import { wordAt, frameToSec } from "../audio/voClock";

/**
 * Craft gate: first 10 s of the real VO timeline + hook picture.
 * Inspect frames every 0.5 s before building the rest.
 */
export const First10s: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frameToSec(frame, fps);
  const w = wordAt(t);

  return (
    <AbsoluteFill>
      <Audio src={staticFile("audio/voiceover.wav")} />
      <Sequence from={0} durationInFrames={10 * fps}>
        <S00_Hook />
      </Sequence>
      {/* debug HUD for craft gate only — strip before master */}
      <div
        style={{
          position: "absolute",
          left: safe.x,
          bottom: 24,
          fontFamily: "IBM Plex Mono, ui-monospace, monospace",
          fontSize: 16,
          color: colors.teal,
          opacity: 0.85,
          zIndex: 50,
        }}
      >
        t={t.toFixed(2)}s · {w ? `“${w.word}”` : "—"}
      </div>
    </AbsoluteFill>
  );
};
