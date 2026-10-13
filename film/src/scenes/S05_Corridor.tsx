import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { Background } from "../components/Background";
import { NetworkGraph } from "../components/Graph";
import { colors, safe, type as typeScale } from "../design/tokens";
import { Eyebrow, RevealText } from "../motion/reveal";
import { enter } from "../motion/easing";

const LEGEND = [
  { label: "Observed", style: "solid" as const, color: colors.teal },
  { label: "External", style: "solid" as const, color: colors.text70 },
  { label: "Inferred", style: "dash" as const, color: colors.amber },
  { label: "Unknown boundary", style: "dash" as const, color: colors.text45 },
];

/** S05 Corridor map — one native graph only (no capture underlay). */
export const S05_Corridor: React.FC = () => {
  const frame = useCurrentFrame();

  const graphIn = interpolate(frame, [6, 24], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });
  // Discrete pan ≤0.6s (@60fps ≈36f) then still
  const panX = interpolate(frame, [30, 66, 66, 400], [30, 0, 0, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const legendIn = interpolate(frame, [40, 70], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });

  return (
    <AbsoluteFill>
      <Background />

      <AbsoluteFill
        style={{
          paddingTop: safe.y,
          paddingLeft: safe.x,
          paddingRight: safe.x,
          zIndex: 3,
        }}
      >
        <div style={{ maxWidth: 1100, margin: "0 auto", textAlign: "center" }}>
          <Eyebrow text="Corridor" start={4} />
          <RevealText
            lines={["Follow the money across institutions."]}
            start={10}
            size={typeScale.caption}
            weight={600}
          />
        </div>
      </AbsoluteFill>

      <AbsoluteFill
        style={{
          opacity: graphIn,
          transform: `translateX(${panX}px) scale(1.08)`,
          zIndex: 2,
        }}
      >
        <NetworkGraph start={8} showLabels />
      </AbsoluteFill>

      <div
        style={{
          position: "absolute",
          left: safe.x,
          bottom: safe.captionBand + 24,
          display: "flex",
          gap: 28,
          opacity: legendIn,
          zIndex: 4,
          fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
          fontSize: 18,
          fontWeight: 600,
          color: colors.text70,
        }}
      >
        {LEGEND.map((item) => (
          <div key={item.label} style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <svg width={36} height={12}>
              <line
                x1={2}
                y1={6}
                x2={34}
                y2={6}
                stroke={item.color}
                strokeWidth={3}
                strokeDasharray={item.style === "dash" ? "6 5" : undefined}
                strokeLinecap="round"
              />
            </svg>
            {item.label}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};
