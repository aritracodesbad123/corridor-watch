import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { Background } from "../components/Background";
import { DeviceFrame } from "../components/DeviceFrame";
import { colors, radius, safe, shadow } from "../design/tokens";
import { enter } from "../motion/easing";
import { fade, useLocalSec } from "../motion/useLocalSec";
import caseData from "../data/case-cw-mid-02.json";

const BRIEF_SECTIONS = [
  {
    key: "why",
    title: "Why this case looks this way",
    body: "SG→PH pass-through with shared device on the corridor; upstream IN→SG feeder within 18 minutes.",
    at: 10.83,
  },
  {
    key: "unknown",
    title: "Still unknown",
    body: "Downstream off-ramp and beneficial owner — coverage partial, not invented.",
    at: 16.27,
  },
  {
    key: "next",
    title: "What to check next",
    body: "Pause for FIU lead; confirm device reuse and corridor counterparties before release.",
    at: 18.5,
  },
] as const;

const PROVENANCE = [
  { label: "gemini tools", at: 26.91 },
  { label: "prefetch", at: 30.78 },
  { label: "grounded", at: 31.74 },
  { label: "fallback", at: 32.94 },
  { label: "gate fail", at: 34.06 },
] as const;

const EVIDENCE_TILES = [
  { id: "E-RISK", label: "Risk score", value: `HIGH · ${caseData.risk}` },
  { id: "E-DEV", label: "Shared device", value: caseData.mule },
] as const;

/**
 * S06 Grounded AI — ~46.54 s local (VO abs 112.86–159.4).
 * Verdict UI → token boundary → Force Gemini brief → provenance → gate fail → evidence chips.
 */
export const S06_Grounded: React.FC = () => {
  const t = useLocalSec();

  const briefUiOp = fade(t, 0, 0.6);
  const ledgerBlockOp = fade(t, 0.19, 0.9);
  const packSlideOp = fade(t, 4.54, 5.4);
  const tokenOp = fade(t, 7.89, 8.8, 12, 13);
  const forceOp = fade(t, 10.83, 11.4);
  const recoOp = fade(t, 21.63, 22.4);
  const lockOp = fade(t, 23.48, 24.5);
  const rejectOp = fade(t, 34.97, 35.8);
  const chipsOp = fade(t, 41.58, 42.5);
  const lockVerdictOp = fade(t, 38.4, 39.5);

  const activeSection =
    t >= 18.5 ? "next" : t >= 16.27 ? "unknown" : t >= 10.83 ? "why" : null;

  const provIndex = PROVENANCE.reduce((acc, p, i) => (t >= p.at ? i : acc), 0);
  const provLabel = PROVENANCE[provIndex]?.label ?? PROVENANCE[0].label;
  const provCritical = provLabel === "gate fail";

  const cursorX = interpolate(t, [10.5, 11.2, 11.8], [1180, 520, 520], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });
  const cursorY = interpolate(t, [10.5, 11.2, 11.8], [280, 420, 420], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });
  const clickRipple = fade(t, 11.15, 11.35) * (1 - fade(t, 11.5, 11.9));

  const streamChars = Math.floor(
    interpolate(t, [11.2, 19.5], [0, 420], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }),
  );

  return (
    <AbsoluteFill>
      <Background />

      {/* Verdict brief capture — left-offset ~68% width */}
      <AbsoluteFill style={{ opacity: briefUiOp, zIndex: 2 }}>
        <div
          style={{
            position: "absolute",
            left: safe.x - 40,
            top: safe.y + 20,
            width: "68%",
            transform: `scale(1)`,
            transformOrigin: "top left",
          }}
        >
          <DeviceFrame src="captures/verdict/brief.jpg" widthPx={1280} heightPx={720} scale={1} />
        </div>
      </AbsoluteFill>

      {/* Raw ledger blocked from model */}
      <GutterCallout
        title="Raw ledger"
        body="Blocked at model boundary — ingest only"
        opacity={ledgerBlockOp}
        top={safe.y + 12}
      />

      {/* Evidence pack → model */}
      <GutterCallout
        title="Evidence pack"
        body="Structured tokens cross the wall"
        opacity={packSlideOp}
        top={safe.y + 120}
        accent={colors.teal}
      />

      {/* Tokenization chip */}
      <div
        style={{
          position: "absolute",
          left: safe.x + 480,
          top: safe.y + 200,
          opacity: tokenOp,
          zIndex: 5,
          padding: "14px 18px",
          borderRadius: radius.card,
          background: colors.card,
          border: `2px solid ${colors.brand}`,
          boxShadow: shadow.card,
          fontFamily: "IBM Plex Mono, ui-monospace, monospace",
          fontSize: 17,
          fontWeight: 700,
          color: colors.ink,
          transform: `translateX(${(1 - tokenOp) * -30}px)`,
        }}
      >
        ACC-MID-SG-MULE →{" "}
        <span style={{ color: colors.brand }}>tok_••••7f2a</span>
      </div>

      {/* Streaming brief overlay (no fixture JSON) */}
      <div
        style={{
          position: "absolute",
          left: safe.x + 40,
          top: safe.y + 280,
          width: 620,
          maxHeight: STAGE_BOTTOM - safe.y - 320,
          overflow: "hidden",
          opacity: forceOp,
          zIndex: 4,
          padding: 24,
          borderRadius: radius.card,
          background: colors.card,
          border: `1px solid ${colors.cardBorder}`,
          boxShadow: shadow.card,
          fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
        }}
      >
        <div
          style={{
            fontSize: 13,
            letterSpacing: "0.1em",
            fontWeight: 800,
            color: colors.tealText,
            marginBottom: 14,
          }}
        >
          AI BRIEF · GROUNDED IN EVIDENCE
        </div>
        {BRIEF_SECTIONS.map((sec) => {
          const hi = activeSection === sec.key;
          const secOp = fade(t, sec.at - 0.2, sec.at + 0.15);
          return (
            <div
              key={sec.key}
              style={{
                marginBottom: 16,
                padding: "14px 16px",
                borderRadius: 12,
                background: hi ? colors.tealSoft : colors.amberTint,
                border: `2px solid ${hi ? colors.teal : "transparent"}`,
                opacity: secOp,
              }}
            >
              <div style={{ fontSize: 16, fontWeight: 800, color: colors.ink, marginBottom: 6 }}>{sec.title}</div>
              <div style={{ fontSize: 17, lineHeight: 1.45, color: colors.inkSecondary, fontWeight: 500 }}>
                {sec.body.slice(0, hi ? streamChars : sec.body.length)}
              </div>
            </div>
          );
        })}
      </div>

      {/* Force Gemini cursor */}
      <svg width={1920} height={1080} style={{ position: "absolute", inset: 0, zIndex: 8, pointerEvents: "none" }}>
        <g opacity={forceOp * fade(t, 10.5, 11, 19.5, 20)}>
          <circle
            cx={cursorX}
            cy={cursorY}
            r={16 + clickRipple * 24}
            fill="none"
            stroke={colors.brand}
            strokeWidth={2}
            strokeOpacity={0.65 * clickRipple}
          />
          <path
            d={`M${cursorX} ${cursorY} l0 26 l6 -5 l4 11 l7 -2 l-4 -11 l9 -2 z`}
            fill={colors.ink}
            stroke={colors.card}
            strokeWidth={1}
          />
        </g>
      </svg>

      {/* Right gutter callouts */}
      <GutterCallout
        title="Recommendation"
        body="Pause for FIU lead"
        opacity={recoOp}
        top={safe.y + 240}
        accent={colors.amber}
      />

      <div
        style={{
          position: "absolute",
          right: safe.x,
          top: safe.y + 360,
          width: 360,
          opacity: lockOp,
          zIndex: 6,
          display: "flex",
          flexDirection: "column",
          gap: 10,
          fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
        }}
      >
        {["Hold payment", "Escalate", "Freeze account"].map((action) => (
          <div
            key={action}
            style={{
              padding: "14px 18px",
              borderRadius: 12,
              background: colors.criticalTint,
              border: `1px solid ${colors.critical}`,
              color: colors.critical,
              fontSize: 18,
              fontWeight: 700,
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            {action}
            <span style={{ fontSize: 14, fontWeight: 800 }}>MODEL ✕</span>
          </div>
        ))}
      </div>

      {/* Provenance chip — large stepping states */}
      <div
        style={{
          position: "absolute",
          right: safe.x,
          top: safe.y + 520,
          width: 380,
          opacity: fade(t, 26.5, 27.2),
          zIndex: 7,
          padding: "22px 26px",
          borderRadius: radius.card,
          background: provCritical ? colors.criticalTint : colors.card,
          border: `3px solid ${provCritical ? colors.critical : colors.brand}`,
          boxShadow: shadow.card,
          fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
          transform: `scale(1)`,
        }}
      >
        <div style={{ fontSize: 13, letterSpacing: "0.08em", fontWeight: 800, color: colors.inkTertiary, marginBottom: 8 }}>
          PROVENANCE
        </div>
        <div
          style={{
            fontSize: 34,
            fontWeight: 800,
            color: provCritical ? colors.critical : colors.ink,
            textTransform: "lowercase",
          }}
        >
          {provLabel}
        </div>
      </div>

      {/* Ungrounded claim reject */}
      <div
        style={{
          position: "absolute",
          right: safe.x,
          top: safe.y + 660,
          width: 380,
          opacity: rejectOp,
          zIndex: 7,
          padding: "18px 20px",
          borderRadius: radius.card,
          background: colors.criticalTint,
          border: `2px solid ${colors.critical}`,
          fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
        }}
      >
        <div style={{ fontSize: 20, fontWeight: 700, color: colors.critical, textDecoration: "line-through" }}>
          Invented Bank D owner
        </div>
        <div style={{ marginTop: 8, fontSize: 16, fontWeight: 700, color: colors.critical }}>Gate fail — no E-chip</div>
      </div>

      {/* Deterministic verdict stands */}
      <div
        style={{
          position: "absolute",
          left: safe.x,
          bottom: safe.captionBand + 36,
          opacity: lockVerdictOp,
          zIndex: 8,
          padding: "16px 28px",
          borderRadius: radius.pill,
          background: colors.ink,
          color: "#fff",
          fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
          fontSize: 36,
          fontWeight: 800,
          letterSpacing: "-0.02em",
          boxShadow: shadow.card,
        }}
      >
        HIGH · {caseData.risk} stands
      </div>

      {/* Evidence chips + leader lines */}
      <svg
        width={1920}
        height={STAGE_BOTTOM}
        style={{ position: "absolute", left: 0, top: 0, zIndex: 6, pointerEvents: "none" }}
      >
        <g opacity={chipsOp}>
          {EVIDENCE_TILES.map((tile, i) => {
            const chipX = 420 + i * 220;
            const chipY = STAGE_BOTTOM - 180;
            const tileX = 920 + i * 200;
            const tileY = STAGE_BOTTOM - 80;
            const pulse = 1;
            return (
              <g key={tile.id}>
                <line
                  x1={chipX + 60}
                  y1={chipY + 20}
                  x2={tileX}
                  y2={tileY}
                  stroke={colors.teal}
                  strokeWidth={2}
                  strokeOpacity={0.5 * pulse}
                />
                <rect
                  x={chipX}
                  y={chipY}
                  width={120}
                  height={36}
                  rx={8}
                  fill={colors.tealSoft}
                  stroke={colors.teal}
                  strokeWidth={1.5}
                />
                <text
                  x={chipX + 60}
                  y={chipY + 24}
                  textAnchor="middle"
                  fill={colors.tealText}
                  fontSize={14}
                  fontWeight={800}
                  fontFamily="Inter, ui-sans-serif, system-ui, sans-serif"
                >
                  {tile.id}
                </text>
                <rect
                  x={tileX - 90}
                  y={tileY - 36}
                  width={180}
                  height={72}
                  rx={12}
                  fill={colors.card}
                  stroke={colors.cardBorder}
                />
                <text
                  x={tileX}
                  y={tileY - 10}
                  textAnchor="middle"
                  fill={colors.inkTertiary}
                  fontSize={13}
                  fontWeight={700}
                  fontFamily="Inter, ui-sans-serif, system-ui, sans-serif"
                >
                  {tile.label}
                </text>
                <text
                  x={tileX}
                  y={tileY + 18}
                  textAnchor="middle"
                  fill={colors.ink}
                  fontSize={16}
                  fontWeight={700}
                  fontFamily="Inter, ui-sans-serif, system-ui, sans-serif"
                >
                  {tile.value}
                </text>
              </g>
            );
          })}
        </g>
      </svg>
    </AbsoluteFill>
  );
};

const STAGE_BOTTOM = 1080 - safe.captionBand;

const GutterCallout: React.FC<{
  title: string;
  body: string;
  opacity: number;
  top: number;
  accent?: string;
}> = ({ title, body, opacity, top, accent = colors.ink }) => (
  <div
    style={{
      position: "absolute",
      right: safe.x,
      top,
      width: 360,
      opacity,
      zIndex: 5,
      padding: "16px 20px",
      borderRadius: 14,
      background: colors.ink,
      color: "#fff",
      fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
      boxShadow: shadow.card,
    }}
  >
    <div style={{ fontSize: 12, letterSpacing: "0.08em", fontWeight: 800, color: accent, marginBottom: 6 }}>
      {title.toUpperCase()}
    </div>
    <div style={{ fontSize: 20, fontWeight: 700, lineHeight: 1.35 }}>{body}</div>
  </div>
);
