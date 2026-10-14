import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { Background } from "../components/Background";
import { DeviceFrame } from "../components/DeviceFrame";
import { colors, safe } from "../design/tokens";
import { enter } from "../motion/easing";
import { fade, useLocalSec } from "../motion/useLocalSec";
import caseData from "../data/case-cw-mid-02.json";
import lotus from "../data/case-cw-lotus-04.json";

/** CW-MID-02 triage row from captures/boxes.json (capture px @ 1920×1080). */
const MID02_ROW = { x: 232, y: 217.234375, w: 319, h: 72.2890625 };

/**
 * S03 — storyboard C: triage across typologies (MID-02 → LOTUS-04 → MID-01 feeder).
 */
export const S03_Triage: React.FC = () => {
  const t = useLocalSec();
  const dur = 75.0 - 35.29;
  const caseIn = 2.6;
  const lotusIn = 14.0;
  const feederIn = 24.4;

  // Discrete punch-in then still (Day-2 shake rule)
  const frameScale = interpolate(t, [0.5, 1.05, 1.051, dur], [0.96, 1.04, 1.04, 1.04], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });

  const queueOpenOp = fade(t, 0.05, 0.35, caseIn, caseIn + 0.9);
  const caseOp = fade(t, caseIn, caseIn + 0.9, lotusIn, lotusIn + 0.8);
  const lotusOp = fade(t, lotusIn, lotusIn + 0.8, feederIn, feederIn + 0.8);
  const queueFeederOp = fade(t, feederIn, feederIn + 0.9);
  const queueOp = Math.max(queueOpenOp, queueFeederOp);

  // Map CW-MID-02 queue row (capture px) → stage px inside DeviceFrame
  const mid = MID02_ROW;
  const imgScale = 1680 / 1920;
  const localX = 960 - 840 + (mid.x + mid.w / 2) * imgScale;
  const localY = 540 - 472.5 + (mid.y + mid.h / 2) * imgScale;
  const targetX = 960 + (localX - 960) * frameScale;
  const targetY = 540 + (localY - 540) * frameScale;

  const cursorX = interpolate(t, [0.8, 1.9, 2.2], [1100, targetX, targetX], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });
  const cursorY = interpolate(t, [0.8, 1.9, 2.2], [220, targetY, targetY], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });
  const click = fade(t, 2.15, 2.3) * (1 - fade(t, 2.5, 2.85));
  const cursorOp = fade(t, 0.5, 0.9, 2.9, 3.5);
  const callouts = fade(t, 5.0, 6.0, feederIn - 0.4, feederIn + 0.3);
  const feederCallouts = fade(t, feederIn + 0.6, feederIn + 1.4);
  const riskCount = Math.round(
    interpolate(t, [8, 12], [0, caseData.risk], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: enter,
    }),
  );

  return (
    <AbsoluteFill>
      <Background />

      <AbsoluteFill
        style={{
          opacity: queueOp,
          transform: callouts > 0.05 || feederCallouts > 0.05 ? "translateX(-180px)" : undefined,
        }}
      >
        <DeviceFrame src="captures/queue/queue.jpg" scale={frameScale * 0.92} objectPosition="0% 0%" />
      </AbsoluteFill>
      <AbsoluteFill
        style={{
          opacity: caseOp,
          transform: callouts > 0.05 ? "translateX(-180px)" : undefined,
        }}
      >
        <DeviceFrame src="captures/case/overview.jpg" scale={frameScale * 0.92} objectPosition="0% 0%" />
      </AbsoluteFill>
      <AbsoluteFill style={{ opacity: lotusOp }}>
        <DeviceFrame
          src="captures/cases/CW-LOTUS-04/overview.jpg"
          scale={frameScale * 0.92}
          objectPosition="0% 0%"
        />
      </AbsoluteFill>
      <div
        style={{
          position: "absolute",
          left: safe.x,
          top: safe.y + 24,
          opacity: lotusOp,
          zIndex: 5,
          padding: "10px 16px",
          borderRadius: 999,
          background: colors.ink,
          color: "#fff",
          fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
          fontSize: 18,
          fontWeight: 700,
        }}
      >
        {lotus.id} · {lotus.pattern.replace(/_/g, " ")}
      </div>

      {/* Highlight ring on CW-MID-02 queue row during open */}
      <div
        style={{
          position: "absolute",
          left: 960 + (960 - 840 + mid.x * imgScale - 960) * frameScale,
          top: 540 + (540 - 472.5 + mid.y * imgScale - 540) * frameScale,
          width: mid.w * imgScale * frameScale,
          height: mid.h * imgScale * frameScale,
          borderRadius: 10,
          border: `2px solid ${colors.teal}`,
          boxShadow: `0 0 0 4px ${colors.tealGlow}`,
          opacity: queueOpenOp * fade(t, 1.6, 2.0, 2.7, 3.2),
          zIndex: 3,
          pointerEvents: "none",
        }}
      />

      <svg
        width={1920}
        height={1080}
        style={{ position: "absolute", inset: 0, zIndex: 4, opacity: cursorOp * queueOpenOp }}
      >
        <circle
          cx={cursorX}
          cy={cursorY}
          r={18 + click * 28}
          fill="none"
          stroke={colors.teal}
          strokeWidth={2}
          strokeOpacity={0.7 * click}
        />
        <path
          d={`M${cursorX} ${cursorY} l0 28 l7 -6 l5 12 l8 -3 l-5 -12 l10 -2 z`}
          fill={colors.text}
          stroke={colors.bg0}
          strokeWidth={1}
        />
      </svg>

      <div
        style={{
          position: "absolute",
          right: safe.x,
          top: safe.y + 100,
          width: 380,
          opacity: callouts * caseOp,
          zIndex: 5,
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}
      >
        {[
          { k: "Case", v: "CW-MID-02 · SG→PH" },
          { k: "Risk", v: `${riskCount} — mule pass-through` },
          {
            k: "Visibility",
            v: `${caseData.network_visibility_pct}% — coverage, not guilt`,
          },
        ].map((row) => (
          <div
            key={row.k}
            style={{
              padding: "18px 20px",
              borderRadius: 14,
              background: colors.ink,
              border: `1px solid ${colors.cardBorder}`,
              boxShadow: "0 12px 32px rgba(11,18,32,0.12)",
              fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
            }}
          >
            <div
              style={{
                fontSize: 14,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                color: "rgba(255,255,255,0.65)",
                fontWeight: 700,
                marginBottom: row.v ? 8 : 0,
              }}
            >
              {row.k}
            </div>
            {row.v ? (
              <div style={{ fontSize: 26, fontWeight: 700, color: "#fff" }}>{row.v}</div>
            ) : null}
          </div>
        ))}
      </div>

      <div
        style={{
          position: "absolute",
          right: safe.x,
          top: safe.y + 100,
          width: 400,
          opacity: feederCallouts * queueFeederOp,
          zIndex: 5,
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}
      >
        {[
          { k: "Feeder case", v: "CW-MID-01 · $9,200 · IN→SG" },
          { k: "Shared device", v: "D-MID-MULE" },
          { k: "Timing", v: "18 minutes earlier" },
        ].map((row) => (
          <div
            key={row.k}
            style={{
              padding: "18px 20px",
              borderRadius: 14,
              background: colors.ink,
              border: `1px solid ${colors.cardBorder}`,
              boxShadow: "0 12px 32px rgba(11,18,32,0.12)",
              fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
            }}
          >
            <div
              style={{
                fontSize: 14,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                color: "rgba(255,255,255,0.65)",
                fontWeight: 700,
                marginBottom: 8,
              }}
            >
              {row.k}
            </div>
            <div style={{ fontSize: 24, fontWeight: 700, color: "#fff" }}>{row.v}</div>
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};
