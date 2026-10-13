import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { Background } from "../components/Background";
import { DeviceFrame } from "../components/DeviceFrame";
import { colors, radius, safe, shadow, type as typeScale } from "../design/tokens";
import { enter } from "../motion/easing";
import { fade, useLocalSec } from "../motion/useLocalSec";

const MATCH_TOTAL = 36;
const BAR_HEIGHTS = [0.42, 0.68, 0.55, 0.88, 0.61, 0.74, 0.48, 0.92, 0.57, 0.79, 0.65, 0.83];

/** S08 — VO 182.36–203.38 (~21.02 s local). Fingerprint → Pattern DNA library. */
export const S08_PatternDNA: React.FC = () => {
  const t = useLocalSec();

  const compress = interpolate(t, [0.5, 7.0], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });
  const networkOp = 1 - fade(t, 6.2, 8.0);
  const fingerprintOp = fade(t, 4.5, 6.5) * (1 - fade(t, 8.5, 10.0));

  const libraryIn = fade(t, 6.8, 8.8);
  // Discrete punch-ins then still holds
  const libraryScale = interpolate(t, [6.8, 7.35, 7.35, 17.5], [1.06, 1.1, 1.1, 1.1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });
  const settleZoom = interpolate(t, [17.5, 18.05, 18.05, 20.5], [1.1, 1.16, 1.16, 1.16], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });
  const plateScale = t >= 17.5 ? settleZoom : libraryScale;

  const cardIn = fade(t, 7.2, 8.6);
  const cardHold = fade(t, 8.6, 17.2) * (1 - fade(t, 17.8, 19.2));
  const cardOp = Math.max(cardIn * cardHold, fade(t, 17.8, 19.0) * 0.35);

  const matchPulse = fade(t, 16.0, 17.0);
  const count = Math.round(
    interpolate(t, [15.5, 18.5], [0, MATCH_TOTAL], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: enter,
    }),
  );

  const highlightRing = fade(t, 17.6, 18.8);
  const wireFade = 1 - fade(t, 19.8, 21.0);
  const alertIn = fade(t, 16.2, 17.2);

  const nodes = [
    [320, 480],
    [620, 420],
    [960, 500],
    [1280, 440],
    [1520, 520],
  ];

  const cx = 960;
  const cy = 460;

  return (
    <AbsoluteFill>
      <Background />

      <AbsoluteFill
        style={{
          opacity: libraryIn,
          zIndex: 1,
          filter: undefined,
        }}
      >
        <DeviceFrame
          src="captures/patterns/library.jpg"
          scale={plateScale}
          objectPosition="50% 20%"
          widthPx={1680}
          heightPx={900}
        />
      </AbsoluteFill>

      {/* CW-005 highlight on library plate when camera settles */}
      <div
        style={{
          position: "absolute",
          left: "50%",
          top: "42%",
          width: 520 * plateScale,
          height: 200 * plateScale,
          transform: "translate(-50%, -50%)",
          borderRadius: radius.card,
          border: `3px solid ${colors.teal}`,
          boxShadow: shadow.card,
          opacity: highlightRing * libraryIn,
          zIndex: 2,
          pointerEvents: "none",
        }}
      />

      {/* Corridor network → compress */}
      <svg
        width={1920}
        height={940}
        style={{
          position: "absolute",
          left: 0,
          top: safe.y,
          opacity: networkOp,
          zIndex: 3,
        }}
      >
        {nodes.slice(0, -1).map(([x1, y1], i) => {
          const [x2, y2] = nodes[i + 1];
          const mx = x1 + (x2 - x1) * (1 - compress) + (cx - x1) * compress;
          const my = y1 + (y2 - y1) * (1 - compress) + (cy - y1) * compress;
          const nx = x2 + (cx - x2) * compress;
          const ny = y2 + (cy - y2) * compress;
          return (
            <line
              key={`e${i}`}
              x1={mx}
              y1={my}
              x2={nx}
              y2={ny}
              stroke={colors.teal}
              strokeWidth={4 - compress * 2}
              strokeOpacity={0.85}
              strokeLinecap="round"
            />
          );
        })}
        {nodes.map(([x, y], i) => {
          const px = x + (cx - x) * compress;
          const py = y + (cy - y) * compress;
          const r = 14 - compress * 8;
          return (
            <circle
              key={`n${i}`}
              cx={px}
              cy={py}
              r={Math.max(4, r)}
              fill={colors.card}
              stroke={colors.teal}
              strokeWidth={2}
            />
          );
        })}
      </svg>

      {/* Fingerprint signal bars */}
      <div
        style={{
          position: "absolute",
          left: "50%",
          top: "38%",
          transform: `translate(-50%, -50%) scale(${0.7 + 0.3 * compress})`,
          opacity: fingerprintOp,
          zIndex: 4,
          display: "flex",
          alignItems: "flex-end",
          gap: 8,
          padding: "24px 32px",
          borderRadius: radius.card,
          background: colors.card,
          border: `1px solid ${colors.cardBorder}`,
          boxShadow: shadow.card,
        }}
      >
        {BAR_HEIGHTS.map((h, i) => (
          <div
            key={i}
            style={{
              width: 14,
              height: 120 * h * fade(t, 4.8 + i * 0.08, 5.4 + i * 0.08),
              borderRadius: 4,
              background: `linear-gradient(180deg, ${colors.teal} 0%, ${colors.brand} 100%)`,
            }}
          />
        ))}
      </div>

      {/* Gutter eyebrow — ink inverse, away from app header */}
      <div
        style={{
          position: "absolute",
          right: safe.x,
          top: safe.y + 16,
          padding: "10px 18px",
          borderRadius: radius.pill,
          background: colors.ink,
          color: colors.canvasHi,
          fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
          fontSize: typeScale.eyebrow,
          fontWeight: 600,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
          opacity: fade(t, 7.5, 8.5),
          boxShadow: shadow.card,
          zIndex: 8,
        }}
      >
        Crime Pattern DNA
      </div>

      {/* CW-005 hero card — fills upper stage */}
      <div
        style={{
          position: "absolute",
          left: safe.x,
          right: safe.x,
          top: safe.y + 48,
          bottom: safe.captionBand + 24,
          padding: 40,
          borderRadius: radius.card,
          background: colors.card,
          border: `1px solid ${colors.cardBorder}`,
          boxShadow: shadow.card,
          opacity: cardOp,
          transform: `scale(${0.94 + 0.06 * cardIn}) translateY(${(1 - cardIn) * 24}px)`,
          zIndex: 5,
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div
          style={{
            fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
            fontSize: 16,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            color: colors.tealText,
            fontWeight: 700,
            marginBottom: 12,
          }}
        >
          Pattern library · multi-hop layering
        </div>
        <div
          style={{
            fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
            fontSize: 52,
            fontWeight: 800,
            color: colors.ink,
            letterSpacing: "-0.02em",
            marginBottom: 16,
          }}
        >
          CW-005
        </div>
        <div
          style={{
            fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
            fontSize: 24,
            color: colors.inkSecondary,
            lineHeight: 1.45,
            maxWidth: 900,
            marginBottom: 28,
          }}
        >
          Fingerprint from confirmed corridor cases. The next alert matches the graph — not a single wire.
        </div>

        <div style={{ display: "flex", alignItems: "flex-end", gap: 6, marginBottom: 32, flex: 1 }}>
          {BAR_HEIGHTS.map((h, i) => (
            <div
              key={i}
              style={{
                flex: 1,
                maxWidth: 28,
                height: `${40 + h * 55}%`,
                borderRadius: 6,
                background: colors.tealSoft,
                border: `1px solid ${colors.cardBorder}`,
                position: "relative",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  position: "absolute",
                  bottom: 0,
                  left: 0,
                  right: 0,
                  height: `${100 * fade(t, 7.5 + i * 0.05, 8.2 + i * 0.05)}%`,
                  background: colors.teal,
                  borderRadius: 5,
                }}
              />
            </div>
          ))}
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "18px 22px",
            borderRadius: radius.pill,
            background: colors.canvasLo,
            border: `1px solid ${colors.cardBorder}`,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <div
              style={{
                padding: "6px 12px",
                borderRadius: 8,
                background: colors.positive,
                color: colors.canvasHi,
                fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
                fontSize: 14,
                fontWeight: 700,
                opacity: alertIn,
                transform: `scale(${0.92 + 0.08 * alertIn})`,
              }}
            >
              New alert
            </div>
            <span
              style={{
                fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
                fontSize: 20,
                fontWeight: 600,
                color: colors.positive,
              }}
            >
              Match · CW-MID-02 network
            </span>
          </div>
          <div
            style={{
              fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
              fontSize: 32,
              fontWeight: 800,
              color: colors.ink,
              transform: `scale(${1 + 0.04 * matchPulse})`,
            }}
          >
            {count} matches
          </div>
        </div>
      </div>

      {/* Single wire — fades while library holds */}
      <div
        style={{
          position: "absolute",
          left: safe.x,
          bottom: safe.captionBand + 48,
          display: "flex",
          alignItems: "center",
          gap: 12,
          opacity: wireFade * fade(t, 18.0, 19.0),
          zIndex: 4,
        }}
      >
        <div
          style={{
            width: 120,
            height: 4,
            borderRadius: 2,
            background: colors.unknown,
            opacity: 0.5,
          }}
        />
        <span
          style={{
            fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
            fontSize: 16,
            color: colors.text45,
            textDecoration: "line-through",
          }}
        >
          Single wire
        </span>
      </div>
    </AbsoluteFill>
  );
};
