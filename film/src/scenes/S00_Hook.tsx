import React from "react";
import { AbsoluteFill, interpolate, useVideoConfig } from "remotion";
import { Background } from "../components/Background";
import { NetworkGraph } from "../components/Graph";
import { colors, safe, type as typeScale } from "../design/tokens";
import { enter } from "../motion/easing";
import { fade, useLocalSec } from "../motion/useLocalSec";

/**
 * S00 Hook — VO 0.00–15.36s.
 * Three exclusive beats (no overlap): thesis → brand → network bloom.
 */
export const S00_Hook: React.FC = () => {
  const t = useLocalSec();
  const { fps } = useVideoConfig();
  const f = (s: number) => Math.round(s * fps);

  // Exclusive phases — never stack brand on graph
  const thesisOp = fade(t, 0.05, 0.4, 8.0, 8.7);
  const networkWord = fade(t, 2.56, 2.95);
  const payOp = fade(t, 0.2, 0.55, 8.0, 8.7);
  const brandOp = fade(t, 8.6, 9.2, 11.7, 12.3);
  const brandTag = fade(t, 9.6, 10.2, 11.7, 12.3);
  const graphOp = fade(t, 12.1, 12.9);

  const payX = interpolate(t, [0.26, 2.5], [420, 1380], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });
  const payY = interpolate(t, [0.26, 2.5], [620, 480], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });
  const pathDraw = interpolate(t, [0.26, 2.5], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });
  const brandScale = interpolate(t, [8.6, 9.4], [0.94, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });

  return (
    <AbsoluteFill>
      <Background intensity={0.85} />

      {/* Beat 1 — thesis + payment arc */}
      <AbsoluteFill
        style={{
          paddingTop: safe.y + 48,
          paddingLeft: safe.x,
          paddingRight: safe.x,
          opacity: thesisOp,
          zIndex: 2,
        }}
      >
        <div style={{ maxWidth: 1480, margin: "0 auto", textAlign: "center" }}>
          <div
            style={{
              fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
              fontSize: typeScale.eyebrow,
              fontWeight: 600,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              color: colors.tealText,
              marginBottom: 20,
              opacity: fade(t, 0.1, 0.45),
            }}
          >
            Cross-border investigation
          </div>
          <div
            style={{
              fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
              fontSize: typeScale.headline,
              fontWeight: 700,
              color: colors.ink,
              letterSpacing: "-0.02em",
              lineHeight: 1.08,
              opacity: fade(t, 0.15, 0.5),
            }}
          >
            The transaction is not the crime.
          </div>
          <div
            style={{
              fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
              fontSize: typeScale.headline,
              fontWeight: 800,
              color: colors.ink,
              letterSpacing: "-0.02em",
              lineHeight: 1.08,
              marginTop: 10,
              opacity: networkWord,
              transform: `translateY(${(1 - networkWord) * 18}px)`,
            }}
          >
            The <span style={{ color: colors.tealText }}>network</span> is.
          </div>
          <div
            style={{
              marginTop: 28,
              fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
              fontSize: typeScale.subhead,
              fontWeight: 500,
              color: colors.inkSecondary,
              opacity: fade(t, 3.8, 4.5, 8.0, 8.7),
            }}
          >
            Suspicious activity hides in the hops — not in the wire.
          </div>
        </div>
      </AbsoluteFill>

      <svg
        width={1920}
        height={1080}
        style={{ position: "absolute", inset: 0, zIndex: 1, opacity: payOp }}
      >
        <path
          d="M420 620 C 720 340, 1080 340, 1380 480"
          fill="none"
          stroke={colors.teal}
          strokeWidth={5}
          strokeLinecap="round"
          strokeDasharray={1200}
          strokeDashoffset={1200 * (1 - pathDraw)}
          opacity={0.85}
        />
        <circle cx={420} cy={620} r={10} fill={colors.card} stroke={colors.teal} strokeWidth={3} />
        <circle cx={payX} cy={payY} r={14} fill={colors.teal} />
        <text
          x={payX}
          y={payY - 28}
          textAnchor="middle"
          fill={colors.ink}
          fontSize={34}
          fontWeight={800}
          fontFamily="Inter, ui-sans-serif, system-ui, sans-serif"
          opacity={fade(t, 0.45, 0.9)}
        >
          $9,050 · SG → PH
        </text>
      </svg>

      {/* Beat 2 — brand alone (clean stage) */}
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          opacity: brandOp,
          zIndex: 4,
          transform: `scale(${brandScale})`,
          background: `radial-gradient(ellipse 70% 50% at 50% 48%, ${colors.canvasHi} 0%, transparent 70%)`,
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
              opacity: brandTag,
              transform: `translateY(${(1 - brandTag) * 14}px)`,
            }}
          >
            Takes the network as the case.
          </div>
        </div>
      </AbsoluteFill>

      {/* Beat 3 — network alone after brand clears */}
      {t >= 11.9 ? (
        <AbsoluteFill style={{ opacity: graphOp, zIndex: 3 }}>
          <NetworkGraph start={f(12.1)} showLabels />
        </AbsoluteFill>
      ) : null}
    </AbsoluteFill>
  );
};
