import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { colors, type as typeScale } from "../design/tokens";
import { enter, fadeUp } from "./easing";

export const RevealText: React.FC<{
  lines: string[];
  start: number;
  stagger?: number;
  size?: number;
  color?: string;
  weight?: number;
  align?: "left" | "center";
  tracking?: number;
}> = ({
  lines,
  start,
  stagger = 5,
  size = typeScale.headline,
  color = colors.text,
  weight = 600,
  align = "center",
  tracking = -0.02,
}) => {
  const frame = useCurrentFrame();
  return (
    <div style={{ textAlign: align }}>
      {lines.map((line, i) => {
        const m = fadeUp(frame, start + i * stagger, 28);
        return (
          <div
            key={i}
            style={{
              fontFamily: 'Inter, ui-sans-serif, system-ui, sans-serif',
              fontSize: size,
              fontWeight: weight,
              color,
              letterSpacing: `${tracking}em`,
              lineHeight: 1.12,
              opacity: m.opacity,
              transform: `translateY(${m.y}px)`,
              filter: m.blur > 0.2 ? `blur(${m.blur}px)` : undefined,
            }}
          >
            {line}
          </div>
        );
      })}
    </div>
  );
};

export const Eyebrow: React.FC<{ text: string; start: number; color?: string }> = ({
  text,
  start,
  color = colors.teal,
}) => {
  const frame = useCurrentFrame();
  const m = fadeUp(frame, start, 18);
  return (
    <div
      style={{
        fontFamily: 'Inter, ui-sans-serif, system-ui, sans-serif',
        fontSize: typeScale.eyebrow,
        fontWeight: 500,
        letterSpacing: "0.08em",
        textTransform: "uppercase",
        color,
        opacity: m.opacity,
        transform: `translateY(${m.y}px)`,
        marginBottom: 18,
      }}
    >
      {text}
    </div>
  );
};

export const exitOpacity = (frame: number, start: number, dur = 16) =>
  interpolate(frame, [start, start + dur], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });
