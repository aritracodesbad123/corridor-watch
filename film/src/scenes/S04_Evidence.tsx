import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { Background } from "../components/Background";
import { DeviceFrame } from "../components/DeviceFrame";
import { colors, radius, safe, shadow } from "../design/tokens";
import { enter } from "../motion/easing";
import { fade, useLocalSec } from "../motion/useLocalSec";
import caseData from "../data/case-cw-mid-02.json";

const DAG_STEPS = [
  { id: "txn", label: "Load payment", at: 11.64 },
  { id: "send", label: "Sender profile", at: null },
  { id: "recv", label: "Receiver profile", at: null },
  { id: "prof", label: "Both profiles", at: 12.72 },
  { id: "bio", label: "Session biometrics", at: null },
  { id: "risk", label: "Risk features", at: 14.19 },
  { id: "dev", label: "Shared devices", at: 15.25 },
  { id: "ben", label: "Shared beneficiaries", at: null },
  { id: "hood", label: "Neighborhood", at: 16.24 },
  { id: "vel", label: "Corridor velocity", at: null },
  { id: "pat", label: "Pattern score", at: null },
  { id: "pack", label: "Evidence pack", at: null },
] as const;

/**
 * S04 Evidence — ~30.94 s local (VO abs 75–105.94).
 * UI construct → ingest wall → 12-step DAG → pack → HIGH·91 → human next step.
 */
export const S04_Evidence: React.FC = () => {
  const t = useLocalSec();

  const uiOp = fade(t, 0, 0.55, 6.5, 7.2);
  const uiFloat = 1;
  const ingestOp = fade(t, 4.0, 4.55, 11.2, 11.8);
  const wallOp = fade(t, 4.4, 5.0, 11.2, 11.8);
  const dagOp = fade(t, 6.97, 8.0, 21.2, 22.0);
  const packOp = fade(t, 17.4, 18.2);
  const verdictOp = fade(t, 18.5, 19.4);
  const pillOp = fade(t, 21.47, 22.2);
  const scoreT = fade(t, 23.91, 24.8);
  const humanOp = fade(t, 25.57, 26.4);
  const strikeOp = fade(t, 28.79, 29.6);

  const score = Math.round(
    interpolate(t, [23.91, 24.6], [0, caseData.risk], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: enter,
    }),
  );

  const uiBehind = uiOp * (1 - dagOp * 0.75);
  // Discrete late punch then still
  const latePush = interpolate(t, [21, 21.55, 21.55, 30.9], [1.0, 1.04, 1.04, 1.04], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });
  const latePan = interpolate(t, [21, 21.55, 21.55, 30.9], [0, -10, -10, -10], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });
  const packFloat = 0;
  const scorePulse = 1;
  const scanX = -80;

  return (
    <AbsoluteFill>
      <Background />

      {/* Continuous scan band through late hold */}
      <div
        style={{
          position: "absolute",
          top: safe.y + 60,
          bottom: safe.captionBand + 20,
          left: scanX,
          width: 140,
          background: `linear-gradient(90deg, transparent, ${colors.tealSoft}, transparent)`,
          opacity: 0.35 * Math.max(dagOp, packOp, scoreT),
          zIndex: 3,
          pointerEvents: "none",
        }}
      />

      {/* 0–4 s: corridor construct — real UI plate */}
      <AbsoluteFill style={{ opacity: uiBehind, zIndex: 1 }}>
        <div
          style={{
            position: "absolute",
            left: "50%",
            top: "46%",
            transform: `translate(-50%, -50%) scale(${uiFloat * 1.02})`,
          }}
        >
          <DeviceFrame
            src={t < 5.5 ? "captures/flow/network.jpg" : "captures/verdict/evidence.jpg"}
            widthPx={1520}
            heightPx={855}
            scale={1}
          />
        </div>
      </AbsoluteFill>

      {/* Ingest vs AI boundary (abs 79–81.9 → local 4–6.9) */}
      <div
        style={{
          position: "absolute",
          left: safe.x,
          top: safe.y + 8,
          right: safe.x + 320,
          display: "flex",
          gap: 16,
          opacity: ingestOp,
          zIndex: 5,
        }}
      >
        <IngestLane t={t} />
        <div
          style={{
            width: 5,
            borderRadius: 4,
            background: colors.ink,
            opacity: wallOp * 0.85,
            alignSelf: "stretch",
            boxShadow: `0 0 0 3px ${colors.brandSoft}`,
          }}
        />
        <div
          style={{
            flex: 1,
            padding: 18,
            borderRadius: radius.card,
            background: colors.card,
            border: `1px solid ${colors.cardBorder}`,
            boxShadow: shadow.card,
            opacity: 0.55,
            fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
          }}
        >
          <div style={{ fontSize: 13, fontWeight: 800, letterSpacing: "0.08em", color: colors.inkTertiary }}>
            AI MODEL
          </div>
          <div style={{ fontSize: 17, color: colors.inkSecondary, margin: "6px 0 12px" }}>Locked until pack</div>
          {["— idle —", "no raw ledger", "tokens only"].map((r) => (
            <div
              key={r}
              style={{
                marginBottom: 8,
                padding: "8px 10px",
                borderRadius: 8,
                background: "#F0F3F8",
                fontSize: 15,
                fontWeight: 600,
                color: colors.inkTertiary,
              }}
            >
              {r}
            </div>
          ))}
        </div>
      </div>

      {/* 12-step DAG — large center grid (≥55% frame) */}
      <div
        style={{
          position: "absolute",
          left: safe.x,
          right: safe.x + 300,
          top: safe.y + 72,
          bottom: safe.captionBand + 24,
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gridTemplateRows: "repeat(3, 1fr)",
          gap: 14,
          opacity: dagOp,
          zIndex: 4,
          transform: `scale(${latePush}) translateY(${latePan}px)`,
          transformOrigin: "50% 40%",
        }}
      >
        {DAG_STEPS.map((s, i) => {
          const lit =
            s.at != null
              ? interpolate(t, [s.at, s.at + 0.32], [0, 1], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                  easing: enter,
                })
              : 0.26;
          const baseIn = interpolate(t, [6.97 + i * 0.08, 7.35 + i * 0.08], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: enter,
          });
          return (
            <div
              key={s.id}
              style={{
                padding: "14px 16px",
                borderRadius: radius.card,
                background: colors.card,
                border: `2px solid ${lit > 0.55 ? colors.teal : colors.cardBorder}`,
                boxShadow: lit > 0.55 ? shadow.card : "0 1px 2px rgba(11,18,32,0.04)",
                opacity: 0.3 + baseIn * 0.7,
                transform: `translateY(${(1 - baseIn) * 10}px) scale(${0.97 + lit * 0.03})`,
                display: "flex",
                flexDirection: "column",
                justifyContent: "center",
                fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
              }}
            >
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  color: lit > 0.55 ? colors.tealText : colors.inkTertiary,
                  marginBottom: 6,
                }}
              >
                Step {i + 1}
              </div>
              <div style={{ fontSize: 20, fontWeight: 700, color: colors.ink, lineHeight: 1.2 }}>{s.label}</div>
            </div>
          );
        })}
      </div>

      {/* Evidence pack + verdict converge */}
      <div
        style={{
          position: "absolute",
          right: safe.x,
          top: safe.y + 88,
          width: 360,
          opacity: packOp,
          zIndex: 6,
          padding: "22px 24px",
          borderRadius: radius.card,
          background: colors.ink,
          color: "#fff",
          boxShadow: shadow.card,
          fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
          transform: `translateY(${(1 - packOp) * 16 + packFloat}px)`,
        }}
      >
        <div style={{ fontSize: 13, letterSpacing: "0.08em", fontWeight: 700, opacity: 0.75, marginBottom: 8 }}>
          EVIDENCE PACK
        </div>
        <div style={{ fontSize: 24, fontWeight: 800, marginBottom: 10, opacity: verdictOp }}>
          Deterministic verdict
        </div>
        <div
          style={{
            fontSize: 44,
            fontWeight: 800,
            color: "#F5C16C",
            opacity: verdictOp,
            letterSpacing: "-0.02em",
          }}
        >
          HIGH · {caseData.risk}
        </div>
      </div>

      {/* Risk pill + count-up + human chip + struck automatic clear */}
      <div
        style={{
          position: "absolute",
          left: safe.x,
          right: safe.x,
          bottom: safe.captionBand + 28,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 20,
          zIndex: 7,
          fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
        }}
      >
        <div
          style={{
            padding: "12px 22px",
            borderRadius: radius.pill,
            background: colors.criticalTint,
            border: `2px solid ${colors.critical}`,
            color: colors.critical,
            fontSize: 22,
            fontWeight: 800,
            opacity: pillOp,
            transform: `scale(${0.92 + pillOp * 0.08})`,
          }}
        >
          HIGH
        </div>
        <div
          style={{
            padding: "12px 22px",
            borderRadius: radius.pill,
            background: colors.card,
            border: `2px solid ${colors.cardBorder}`,
            boxShadow: shadow.card,
            fontSize: 32,
            fontWeight: 800,
            color: colors.ink,
            opacity: scoreT,
            minWidth: 88,
            textAlign: "center",
            transform: `scale(${scorePulse})`,
          }}
        >
          {score}
        </div>
        <div
          style={{
            padding: "14px 24px",
            borderRadius: radius.pill,
            background: colors.tealSoft,
            border: `2px solid ${colors.teal}`,
            color: colors.tealText,
            fontSize: 20,
            fontWeight: 700,
            opacity: humanOp,
          }}
        >
          Human decision next
        </div>
        <div
          style={{
            position: "relative",
            padding: "14px 24px",
            borderRadius: radius.pill,
            background: "#F0F3F8",
            color: colors.inkTertiary,
            fontSize: 20,
            fontWeight: 600,
            opacity: strikeOp,
          }}
        >
          Automatic clear
          <div
            style={{
              position: "absolute",
              left: 8,
              right: 8,
              top: "50%",
              height: 3,
              background: colors.critical,
              transform: `scaleX(${interpolate(t, [28.79, 29.2], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: enter,
              })})`,
              transformOrigin: "left center",
            }}
          />
        </div>
      </div>
    </AbsoluteFill>
  );
};

const IngestLane: React.FC<{ t: number }> = ({ t }) => {
  const rows = [
    `TXN · ${caseData.corridor} · $${caseData.amount.toLocaleString()}`,
    "ACC-MID-SG-MULE",
    `${caseData.mule} · shared`,
    "Risk features · stream",
  ];
  return (
    <div
      style={{
        flex: 1,
        padding: 18,
        borderRadius: radius.card,
        background: colors.card,
        border: `1px solid ${colors.cardBorder}`,
        boxShadow: shadow.card,
        fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
      }}
    >
      <div style={{ fontSize: 13, fontWeight: 800, letterSpacing: "0.08em", color: colors.brand }}>INGEST</div>
      <div style={{ fontSize: 17, color: colors.inkSecondary, margin: "6px 0 12px" }}>Raw ledger rows</div>
      {rows.map((r, i) => {
        const on = interpolate(t, [4.2 + i * 0.22, 4.65 + i * 0.22], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        return (
          <div
            key={r}
            style={{
              marginBottom: 8,
              padding: "10px 12px",
              borderRadius: 10,
              background: colors.amberTint,
              color: colors.ink,
              fontSize: 15,
              fontWeight: 600,
              opacity: 0.35 + on * 0.65,
              transform: `translateX(${(1 - on) * 14}px)`,
            }}
          >
            {r}
          </div>
        );
      })}
    </div>
  );
};
