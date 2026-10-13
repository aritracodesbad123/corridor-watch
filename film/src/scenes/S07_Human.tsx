import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { Background } from "../components/Background";
import { DeviceFrame } from "../components/DeviceFrame";
import { colors, radius, safe, shadow, type as typeScale } from "../design/tokens";
import { enter } from "../motion/easing";
import { fade, useLocalSec } from "../motion/useLocalSec";
import caseData from "../data/case-cw-lotus-04.json";

const ACTIONS = ["hold_payment", "escalate_fiu", "freeze_account"] as const;
const LABELS: Record<(typeof ACTIONS)[number], string> = {
  hold_payment: "Hold payment",
  escalate_fiu: "Escalate to FIU",
  freeze_account: "Freeze account",
};

/** S07 — VO 159.4–182.36 (~22.96 s local). Human authorization + workflow UI. */
export const S07_Human: React.FC = () => {
  const t = useLocalSec();

  // Discrete eased punch-in then still hold (no continuous drift — Day-1/2 shake fix).
  const heroScale = interpolate(t, [0, 0.55, 0.55, 22], [1.0, 1.06, 1.06, 1.06], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });

  const matrixIn = fade(t, 2.2, 3.2);
  const matrixOut = fade(t, 9.2, 10.4);
  const matrixOp = matrixIn * (1 - matrixOut);

  const analystLock = fade(t, 6.5, 7.4);
  const fiuHighlight = fade(t, 2.4, 3.0);

  const workflowFocus = fade(t, 8.8, 10.0);
  const holdSelect = fade(t, 9.4, 10.2);
  const stamp = fade(t, 13.6, 14.6);
  const audit = fade(t, 14.8, 15.8);
  const footnote = fade(t, 18.5, 19.4);
  const splitIn = fade(t, 19.6, 20.5);
  const splitPerson = fade(t, 21.0, 21.8);

  const cursorX = interpolate(t, [9.0, 10.5, 11.0], [1180, 920, 920], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });
  const cursorY = interpolate(t, [9.0, 10.5, 11.0], [380, 520, 520], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });
  const cursorOp = fade(t, 8.6, 9.2, 11.4, 12.0) * workflowFocus;

  return (
    <AbsoluteFill>
      <Background />

      <AbsoluteFill style={{ opacity: 0.35 + 0.65 * workflowFocus, zIndex: 1 }}>
        <DeviceFrame
          src="captures/decision/workflow.jpg"
          scale={heroScale}
          objectPosition="0% 0%"
          widthPx={1728}
          heightPx={972}
        />
      </AbsoluteFill>

      {/* FIU rail indicator — top of frame, clear of workflow buttons */}
      <div
        style={{
          position: "absolute",
          left: Math.round(safe.x + 48),
          top: Math.round(safe.y + 8),
          padding: "8px 16px",
          borderRadius: radius.pill,
          background: colors.brandSoft,
          border: `1px solid ${colors.cardBorder}`,
          boxShadow: shadow.card,
          fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
          fontSize: 15,
          fontWeight: 600,
          color: colors.brand,
          opacity: workflowFocus * fade(t, 11.0, 11.8) * (1 - matrixOp),
          zIndex: 4,
        }}
      >
        Decision rail · FIU lead
      </div>

      {/* Role matrix */}
      <div
        style={{
          position: "absolute",
          left: safe.x,
          top: safe.y + 8,
          width: 520,
          padding: 20,
          borderRadius: radius.card,
          background: colors.card,
          border: `1px solid ${colors.cardBorder}`,
          boxShadow: shadow.card,
          opacity: matrixOp,
          transform: `translateY(${(1 - matrixIn) * 24}px) scale(${0.96 + 0.04 * matrixIn})`,
          zIndex: 5,
        }}
      >
        <div
          style={{
            fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
            fontSize: typeScale.eyebrow,
            fontWeight: 600,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            color: colors.tealText,
            marginBottom: 14,
          }}
        >
          Consequential actions
        </div>
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
            fontSize: 14,
          }}
        >
          <thead>
            <tr>
              <th style={{ textAlign: "left", padding: "6px 4px", color: colors.text45 }} />
              {ACTIONS.map((a) => (
                <th
                  key={a}
                  style={{
                    textAlign: "center",
                    padding: "6px 4px",
                    color: colors.inkSecondary,
                    fontWeight: 600,
                    fontSize: 12,
                  }}
                >
                  {LABELS[a]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(["Analyst", "FIU lead"] as const).map((role) => {
              const isFiU = role === "FIU lead";
              const rowHi = isFiU ? fiuHighlight : 0;
              return (
                <tr
                  key={role}
                  style={{
                    background: isFiU ? `rgba(39,99,232,${0.06 + 0.08 * rowHi})` : undefined,
                  }}
                >
                  <td
                    style={{
                      padding: "10px 4px",
                      fontWeight: 700,
                      color: colors.ink,
                    }}
                  >
                    {role}
                  </td>
                  {ACTIONS.map((a) => {
                    const refused = !isFiU && analystLock > 0.2;
                    const allowed = isFiU;
                    return (
                      <td key={a} style={{ textAlign: "center", padding: "10px 4px" }}>
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            justifyContent: "center",
                            minWidth: 72,
                            padding: "4px 8px",
                            borderRadius: 8,
                            fontSize: 12,
                            fontWeight: 700,
                            letterSpacing: "0.04em",
                            textTransform: "uppercase",
                            color: refused ? colors.critical : allowed ? colors.positive : colors.text45,
                            background: refused
                              ? colors.criticalTint
                              : allowed
                                ? "rgba(30,158,106,0.12)"
                                : colors.canvasLo,
                            border: `1px solid ${refused ? "rgba(214,64,79,0.25)" : allowed ? "rgba(30,158,106,0.25)" : colors.cardBorder}`,
                            opacity: refused ? analystLock : 1,
                          }}
                        >
                          {refused ? "Refused" : isFiU ? "Allowed" : "—"}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* hold_payment row highlight on workflow */}
      <div
        style={{
          position: "absolute",
          left: 960 - 840 + 680 * (1728 / 1920) * heroScale,
          top: 540 - 486 + 480 * (972 / 1080) * heroScale,
          width: 520 * (1728 / 1920) * heroScale,
          height: 56 * (972 / 1080) * heroScale,
          borderRadius: 10,
          border: `2px solid ${colors.amber}`,
          boxShadow: `0 4px 16px rgba(200,112,16,0.18)`,
          opacity: holdSelect * workflowFocus,
          zIndex: 3,
          pointerEvents: "none",
        }}
      />

      <svg
        width={1920}
        height={1080}
        style={{ position: "absolute", inset: 0, zIndex: 6, opacity: cursorOp, pointerEvents: "none" }}
      >
        <circle cx={cursorX} cy={cursorY} r={10} fill={colors.ink} opacity={0.85} />
        <circle
          cx={cursorX}
          cy={cursorY}
          r={18 + 6 * holdSelect}
          fill="none"
          stroke={colors.brand}
          strokeWidth={2}
          opacity={holdSelect * 0.7}
        />
      </svg>

      {/* AUTHORIZED — lower-right safe zone; never over audit JSON */}
      <div
        style={{
          position: "absolute",
          right: Math.round(safe.x),
          top: Math.round(160),
          padding: "12px 22px",
          border: `3px solid ${colors.positive}`,
          color: colors.positive,
          fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
          fontSize: 20,
          fontWeight: 800,
          letterSpacing: "0.14em",
          textTransform: "uppercase",
          transform: `scale(${0.88 + 0.12 * stamp})`,
          opacity: stamp * workflowFocus * (1 - audit),
          boxShadow: shadow.card,
          background: colors.card,
          zIndex: 7,
        }}
      >
        Authorized
      </div>

      <div
        style={{
          position: "absolute",
          left: safe.x,
          right: safe.x,
          bottom: safe.captionBand + 28,
          padding: "14px 20px",
          borderRadius: radius.pill,
          background: colors.card,
          border: `1px solid ${colors.cardBorder}`,
          boxShadow: shadow.card,
          opacity: audit,
          transform: `translateY(${(1 - audit) * 12}px)`,
          zIndex: 7,
          fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
          fontSize: 20,
          color: colors.inkSecondary,
          textAlign: "center",
        }}
      >
        <span style={{ color: colors.tealText, fontWeight: 700 }}>Audit · </span>
        FIU lead authorized hold_payment on {caseData.id} · 14:52
      </div>

      <div
        style={{
          position: "absolute",
          left: safe.x + 360,
          right: safe.x + 360,
          bottom: safe.captionBand + 88,
          display: "flex",
          gap: 16,
          justifyContent: "center",
          zIndex: 6,
        }}
      >
        <div
          style={{
            flex: 1,
            maxWidth: 420,
            padding: "16px 20px",
            borderRadius: radius.card,
            background: colors.tealSoft,
            border: `1px solid ${colors.cardBorder}`,
            boxShadow: shadow.card,
            opacity: splitIn,
            transform: `translateX(${(1 - splitIn) * -20}px)`,
            fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
            fontSize: 18,
            fontWeight: 600,
            color: colors.tealText,
            textAlign: "center",
          }}
        >
          Gemini recommended
        </div>
        <div
          style={{
            flex: 1,
            maxWidth: 420,
            padding: "16px 20px",
            borderRadius: radius.card,
            background: colors.amberTint,
            border: `1px solid ${colors.cardBorder}`,
            boxShadow: shadow.card,
            opacity: splitPerson,
            transform: `translateX(${(1 - splitPerson) * 20}px)`,
            fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
            fontSize: 18,
            fontWeight: 700,
            color: colors.amber,
            textAlign: "center",
          }}
        >
          A person decided
        </div>
      </div>

      {/* Disclosure — bottom band above captions; never over header tabs */}
      <div
        style={{
          position: "absolute",
          left: Math.round(safe.x),
          bottom: Math.round(safe.captionBand + 100),
          padding: "10px 16px",
          borderRadius: radius.pill,
          background: colors.ink,
          color: colors.canvasHi,
          fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
          fontSize: 15,
          fontWeight: 600,
          opacity: footnote * (1 - splitIn),
          boxShadow: shadow.card,
          zIndex: 8,
          maxWidth: 420,
          lineHeight: 1.35,
        }}
      >
        Console hold — not a core-banking freeze
      </div>
    </AbsoluteFill>
  );
};
