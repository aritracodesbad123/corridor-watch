import React from "react";
import { AbsoluteFill, interpolate, useVideoConfig } from "remotion";
import { Background } from "../components/Background";
import { colors, safe, type as typeScale } from "../design/tokens";
import { enter } from "../motion/easing";
import { useLocalSec } from "../motion/useLocalSec";

/**
 * S02 — Brand bridge between A and B (music-only gap; short).
 * Timings scale to local duration so a 0.75s cut still lands a logo beat.
 */
export const S02_Brand: React.FC = () => {
  const t = useLocalSec();
  const { durationInFrames, fps } = useVideoConfig();
  const dur = Math.max(durationInFrames / fps, 0.35);

  const collapse = interpolate(t, [0, dur * 0.45], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });
  const logoIn = interpolate(t, [dur * 0.2, dur * 0.55], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });
  const sweep = interpolate(t, [dur * 0.35, dur], [-0.2, 1.2], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const tagIn = interpolate(t, [dur * 0.45, Math.min(dur * 0.85, dur - 0.05)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });

  return (
    <AbsoluteFill>
      <Background />

      <svg
        width={1920}
        height={1080}
        style={{ position: "absolute", inset: 0, opacity: collapse, zIndex: 1 }}
      >
        {[
          [620, 540],
          [960, 540],
          [1300, 540],
        ].map(([x, y], i) => (
          <circle
            key={i}
            cx={960 + (x - 960) * collapse}
            cy={y}
            r={10 * collapse}
            fill={colors.teal}
            opacity={0.7}
          />
        ))}
        <line
          x1={960 + (620 - 960) * collapse}
          y1={540}
          x2={960 + (1300 - 960) * collapse}
          y2={540}
          stroke={colors.teal}
          strokeWidth={2}
          strokeOpacity={0.5 * collapse}
        />
      </svg>

      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          zIndex: 2,
          opacity: logoIn,
          transform: `scale(${0.92 + 0.08 * logoIn})`,
        }}
      >
        <div style={{ textAlign: "center", position: "relative", padding: "0 48px" }}>
          <div
            style={{
              position: "absolute",
              inset: "-40px -80px",
              background: `linear-gradient(105deg, transparent ${sweep * 100 - 12}%, ${colors.tealGlow} ${sweep * 100}%, transparent ${sweep * 100 + 12}%)`,
              pointerEvents: "none",
            }}
          />
          <div
            style={{
              fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
              fontSize: 96,
              fontWeight: 700,
              letterSpacing: "-0.03em",
              color: colors.text,
              lineHeight: 1.05,
            }}
          >
            Corridor Watch
          </div>
          <div
            style={{
              marginTop: 28,
              maxWidth: 980,
              marginLeft: "auto",
              marginRight: "auto",
              fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
              fontSize: typeScale.subhead,
              fontWeight: 500,
              color: colors.text70,
              letterSpacing: "-0.01em",
              lineHeight: 1.35,
              opacity: tagIn,
              transform: `translateY(${(1 - tagIn) * 16}px)`,
            }}
          >
            Investigate the corridor. Preserve the evidence. Keep the decision human.
          </div>
        </div>
      </AbsoluteFill>

      <div
        style={{
          position: "absolute",
          left: safe.x,
          right: safe.x,
          bottom: safe.y,
          textAlign: "center",
          opacity: tagIn * 0.85,
          fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
          fontSize: 22,
          color: colors.teal,
          letterSpacing: "0.04em",
          fontWeight: 600,
        }}
      >
        One alert → a defensible decision
      </div>
    </AbsoluteFill>
  );
};
