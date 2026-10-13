import React from "react";
import { AbsoluteFill } from "remotion";
import { colors } from "../design/tokens";

/** Static light stage — no continuous drift/orbit (Day-2 shake kill). */
export const Background: React.FC<{ intensity?: number }> = ({ intensity = 1 }) => {
  return (
    <AbsoluteFill style={{ background: colors.canvas, overflow: "hidden" }}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse 80% 60% at 50% 40%, ${colors.canvasHi} 0%, ${colors.canvasLo} 55%, ${colors.canvas} 100%)`,
          opacity: intensity,
        }}
      />
      <AbsoluteFill
        style={{
          background: `radial-gradient(circle at 70% 24%, ${colors.blobBlue} 0%, transparent 46%)`,
        }}
      />
      <AbsoluteFill
        style={{
          background: `radial-gradient(circle at 30% 76%, ${colors.blobTeal} 0%, transparent 44%)`,
        }}
      />
      <AbsoluteFill
        style={{
          backgroundImage: `linear-gradient(${colors.grid} 1px, transparent 1px), linear-gradient(90deg, ${colors.grid} 1px, transparent 1px)`,
          backgroundSize: "40px 40px",
          backgroundPosition: "0px 0px",
          maskImage: "radial-gradient(ellipse at center, #000 32%, transparent 88%)",
          opacity: 0.7 * intensity,
        }}
      />
    </AbsoluteFill>
  );
};
