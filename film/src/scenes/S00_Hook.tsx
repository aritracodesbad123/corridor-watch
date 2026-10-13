import React from "react";
import { AbsoluteFill, interpolate, useVideoConfig } from "remotion";
import { Background } from "../components/Background";
import { NetworkGraph } from "../components/Graph";
import { colors, safe, type as typeScale } from "../design/tokens";
import { enter } from "../motion/easing";
import { fade, useLocalSec } from "../motion/useLocalSec";

/**
 * S00 — Storyboard A then bridge into B.
 * 0–8s: Corridor Watch title on clean plain stage (no graph / no UI).
 * Title fully exits before any network graphic enters.
 */
export const S00_Hook: React.FC = () => {
  const t = useLocalSec();
  const { fps } = useVideoConfig();
  const f = (s: number) => Math.round(s * fps);

  const titleIn = fade(t, 0.15, 0.7);
  const titleHold = fade(t, 0.7, 7.0) * (1 - fade(t, 7.2, 8.0));
  const titleOp = Math.max(titleIn * titleHold, fade(t, 0.15, 0.7) * (1 - fade(t, 7.2, 8.0)));
  const tagOp = fade(t, 1.4, 2.2) * (1 - fade(t, 7.2, 8.0));

  // After title clears: short problem bridge (payment arc) then network — never under title
  const problemOp = fade(t, 8.1, 8.8, 12.0, 12.8);
  const graphOp = fade(t, 12.4, 13.2);

  const brandScale = interpolate(t, [0.15, 0.7, 0.7, 7.2], [0.96, 1, 1, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });

  return (
    <AbsoluteFill>
      {/* Plain stage for title — no decorative graph behind brand */}
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

      {/* Problem bridge — only after title exit */}
      <AbsoluteFill style={{ opacity: problemOp, zIndex: 2 }}>
        <Background intensity={0.7} />
        <div
          style={{
            position: "absolute",
            left: safe.x,
            right: safe.x,
            top: safe.y + 120,
            textAlign: "center",
            fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
            fontSize: 52,
            fontWeight: 700,
            color: colors.ink,
            letterSpacing: "-0.02em",
          }}
        >
          The transaction is not the crime.
        </div>
        <div
          style={{
            position: "absolute",
            left: safe.x,
            right: safe.x,
            top: safe.y + 200,
            textAlign: "center",
            fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
            fontSize: 36,
            fontWeight: 500,
            color: colors.inkSecondary,
          }}
        >
          The network is.
        </div>
      </AbsoluteFill>

      {t >= 12.2 ? (
        <AbsoluteFill style={{ opacity: graphOp, zIndex: 3 }}>
          <NetworkGraph start={f(12.4)} showLabels />
        </AbsoluteFill>
      ) : null}
    </AbsoluteFill>
  );
};
