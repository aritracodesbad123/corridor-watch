import React from "react";
import { AbsoluteFill, interpolate, useVideoConfig } from "remotion";
import { colors, type as typeScale } from "../design/tokens";
import { enter } from "../motion/easing";
import { fade, useLocalSec } from "../motion/useLocalSec";

/**
 * S00 — Storyboard A: clean Corridor Watch title (no graph / no UI).
 * Duration follows scenes.json (section A VO); timings scale to local length.
 */
export const S00_Hook: React.FC = () => {
  const t = useLocalSec();
  const { durationInFrames, fps } = useVideoConfig();
  const dur = durationInFrames / fps;
  const inEnd = Math.min(0.55, dur * 0.12);
  const outStart = Math.max(dur - 0.55, inEnd + 0.2);
  const tagIn = Math.min(1.2, dur * 0.25);
  const tagInEnd = Math.min(tagIn + 0.5, outStart - 0.05);

  const titleOp = fade(t, 0.12, inEnd) * (1 - fade(t, outStart, dur));
  const tagOp = fade(t, tagIn, tagInEnd) * (1 - fade(t, outStart, dur));
  const brandScale = interpolate(t, [0.12, inEnd], [0.96, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });

  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ background: colors.canvas }} />
      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse 70% 50% at 50% 48%, ${colors.canvasHi} 0%, ${colors.canvas} 70%)`,
          opacity: titleOp,
        }}
      />

      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          opacity: titleOp,
          zIndex: 4,
          transform: `scale(${brandScale})`,
        }}
      >
        <div style={{ textAlign: "center", maxWidth: 1200, padding: "0 48px" }}>
          <div
            style={{
              fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
              fontSize: 104,
              fontWeight: 800,
              color: colors.ink,
              letterSpacing: "-0.03em",
              lineHeight: 1.05,
            }}
          >
            Corridor Watch
          </div>
          <div
            style={{
              marginTop: 28,
              fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
              fontSize: typeScale.subhead,
              fontWeight: 500,
              color: colors.inkSecondary,
              opacity: tagOp,
            }}
          >
            Investigate the corridor. Keep the decision human.
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
