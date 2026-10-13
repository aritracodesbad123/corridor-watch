import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { Background } from "../components/Background";
import { DeviceFrame } from "../components/DeviceFrame";
import { colors, radius, safe, shadow, type as typeScale } from "../design/tokens";
import { enter } from "../motion/easing";
import { fade } from "../motion/useLocalSec";

/**
 * Pass-2 review slice — absolute VO 81.0–96.0 mapped to local 0–15 s.
 * Ingest wall exits before DAG lighting; real UI punch-in; big step grid.
 */
const STEPS = [
  { id: "pay", label: "Load payment", at: 5.64 },
  { id: "prof", label: "Both profiles", at: 6.72 },
  { id: "risk", label: "Risk features", at: 8.19 },
  { id: "dev", label: "Shared devices", at: 9.25 },
  { id: "hood", label: "Neighborhood", at: 10.24 },
  { id: "ver", label: "Deterministic verdict", at: 12.4 },
] as const;

export const Pass2DagSlice: React.FC = () => {
  const frame = useCurrentFrame();
  const t = frame / 60;

  const ingestOp = fade(t, 0, 0.5, 4.8, 5.5);
  const wallOp = fade(t, 0.4, 1.0, 4.8, 5.5);
  const dagOp = fade(t, 1.0, 1.8);
  const uiOp = fade(t, 0.15, 0.7);
  const uiScale = interpolate(t, [1.0, 1.55, 1.55, 14.5], [0.98, 1.04, 1.04, 1.04], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });
  const packOp = fade(t, 12.8, 13.6);

  return (
    <AbsoluteFill>
      <Background />

      <AbsoluteFill style={{ opacity: uiOp * (0.45 + dagOp * 0.45) }}>
        <div
          style={{
            position: "absolute",
            left: "42%",
            top: "48%",
            transform: `translate(-50%, -50%) scale(${uiScale})`,
          }}
        >
          <DeviceFrame src="captures/flow/network.jpg" scale={1} widthPx={1480} heightPx={832} />
        </div>
      </AbsoluteFill>

      <div
        style={{
          position: "absolute",
          left: safe.x,
          top: safe.y + 12,
          right: safe.x + 360,
          display: "flex",
          gap: 18,
          opacity: ingestOp,
          zIndex: 3,
        }}
      >
        <Lane
          title="Ingest"
          subtitle="Raw ledger rows"
          active
          rows={["TXN · SG→PH · $9,050", "ACC-MID-SG-MULE", "D-MID-MULE · shared", "Risk features · stream"]}
          t={t}
        />
        <div
          style={{
            width: 4,
            borderRadius: 4,
            background: colors.ink,
            opacity: wallOp * 0.9,
            boxShadow: `0 0 0 4px ${colors.brandSoft}`,
            alignSelf: "stretch",
          }}
        />
        <Lane title="AI model" subtitle="Locked until pack" active={false} rows={["— idle —", "no raw ledger", "tokens only"]} t={t} />
      </div>

      <div
        style={{
          position: "absolute",
          left: safe.x,
          right: safe.x + 340,
          top: 210,
          bottom: safe.captionBand + 24,
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gridTemplateRows: "repeat(2, 1fr)",
          gap: 18,
          opacity: dagOp,
          zIndex: 4,
        }}
      >
        {STEPS.map((s, i) => {
          const on = interpolate(t, [s.at, s.at + 0.28], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: enter,
          });
          return (
            <div
              key={s.id}
              style={{
                padding: "22px 24px",
                borderRadius: radius.card,
                background: colors.card,
                border: `2px solid ${on > 0.5 ? colors.teal : colors.cardBorder}`,
                boxShadow: shadow.card,
                transform: `translateY(${(1 - on) * 12}px) scale(${0.96 + on * 0.04})`,
                opacity: 0.28 + on * 0.72,
                display: "flex",
                flexDirection: "column",
                justifyContent: "center",
              }}
            >
              <div
                style={{
                  fontSize: 14,
                  fontWeight: 700,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  color: on > 0.5 ? colors.tealText : colors.inkTertiary,
                  marginBottom: 8,
                  fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
                }}
              >
                Step {i + 1}
              </div>
              <div
                style={{
                  fontSize: 28,
                  fontWeight: 700,
                  color: colors.ink,
                  fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
                }}
              >
                {s.label}
              </div>
            </div>
          );
        })}
      </div>

      <div
        style={{
          position: "absolute",
          right: safe.x,
          top: safe.y + 100,
          width: 340,
          opacity: packOp,
          zIndex: 5,
          padding: "22px 24px",
          borderRadius: radius.card,
          background: colors.ink,
          color: "#fff",
          boxShadow: shadow.card,
          fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
        }}
      >
        <div style={{ fontSize: 13, letterSpacing: "0.08em", fontWeight: 700, opacity: 0.7, marginBottom: 8 }}>
          EVIDENCE PACK
        </div>
        <div style={{ fontSize: 28, fontWeight: 800, marginBottom: 12 }}>Deterministic verdict</div>
        <div style={{ fontSize: 42, fontWeight: 800, color: "#F5C16C" }}>HIGH · 91</div>
        <div style={{ marginTop: 10, fontSize: 16, opacity: 0.75 }}>Human decision next — not an automatic clear</div>
      </div>

      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          height: safe.captionBand,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 10,
          pointerEvents: "none",
        }}
      >
        <div
          style={{
            maxWidth: 1200,
            padding: "12px 22px",
            borderRadius: 14,
            background: "rgba(255,255,255,0.94)",
            border: `1px solid ${colors.cardBorder}`,
            boxShadow: "0 8px 24px rgba(11,18,32,0.10)",
            color: colors.ink,
            fontSize: typeScale.caption,
            fontWeight: 600,
            textAlign: "center",
            fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
          }}
        >
          {captionFor(t)}
        </div>
      </div>
    </AbsoluteFill>
  );
};

function captionFor(t: number): string {
  const abs = t + 81;
  if (abs < 81.97) return "Ingest never calls Gemini.";
  if (abs < 86.64) return "A twelve-step investigation DAG";
  if (abs < 91.24) return "loads the payment, both profiles, risk features, shared devices,";
  return "and the neighborhood, then drafts a deterministic verdict from the evidence pack.";
}

const Lane: React.FC<{
  title: string;
  subtitle: string;
  active: boolean;
  rows: string[];
  t: number;
}> = ({ title, subtitle, active, rows, t }) => (
  <div
    style={{
      flex: 1,
      padding: 20,
      borderRadius: radius.card,
      background: colors.card,
      border: `1px solid ${colors.cardBorder}`,
      boxShadow: shadow.card,
      opacity: active ? 1 : 0.55,
      fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
    }}
  >
    <div style={{ fontSize: 13, fontWeight: 800, letterSpacing: "0.08em", color: active ? colors.brand : colors.inkTertiary }}>
      {title.toUpperCase()}
    </div>
    <div style={{ fontSize: 18, color: colors.inkSecondary, margin: "6px 0 14px" }}>{subtitle}</div>
    {rows.map((r, i) => {
      const on = active
        ? interpolate(t, [0.5 + i * 0.25, 0.9 + i * 0.25], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          })
        : 0.4;
      return (
        <div
          key={r}
          style={{
            marginBottom: 8,
            padding: "10px 12px",
            borderRadius: 10,
            background: active ? colors.amberTint : "#F0F3F8",
            color: colors.ink,
            fontSize: 16,
            fontWeight: 600,
            opacity: 0.35 + on * 0.65,
            transform: `translateX(${(1 - on) * 12}px)`,
          }}
        >
          {r}
        </div>
      );
    })}
  </div>
);
