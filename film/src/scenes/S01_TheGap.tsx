import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { Background } from "../components/Background";
import { DeviceFrame } from "../components/DeviceFrame";
import { colors, radius, safe, shadow } from "../design/tokens";
import { enter } from "../motion/easing";
import { fade, useLocalSec } from "../motion/useLocalSec";
import caseData from "../data/case-cw-mid-02.json";

const VO0 = 15.36;
const DUR = 34.95 - VO0;
const STAGE_BOTTOM = 1080 - safe.captionBand;
const CX = 960;
const CY = 520;

/**
 * S01 The gap — ~19.59 s local (VO abs 15.36–34.95).
 * Rule on one wire → rings → timeline (sequential) → shared device (sequential links) 
 * → queue cutaway (camera push) → alert card + drifting ghosts.
 * Visual event every 2-3s to eliminate static layout.
 */
export const S01_TheGap: React.FC = () => {
  const t = useLocalSec();
  const drift = 0; // Day-2: no continuous sin drift
  const dash = 0;
  // Discrete punch-in ≤0.6s then still hold
  const camPush = interpolate(t, [0, 0.55, 0.55, DUR], [1.0, 1.04, 1.04, 1.04], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });
  const camPan = interpolate(t, [0, 0.55, 0.55, DUR], [0, -8, -8, -8], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });
  const scanX = -100;

  // Phase 1: Rule threshold (0-4s)
  const ruleOp = fade(t, 0, 0.35, 3.6, 4.2);
  
  // Phase 2: Rings fan out (4-8s)
  const ringsOp = fade(t, 4.04, 4.55, 12.0, 12.8);
  const ringCount = 5;
  const ringPulse = 1;
  
  // Phase 3: Timeline chips - SEQUENTIAL per VO item (8-12s)
  // "Funds can arrive" → chip 1
  // "rest for minutes" → chip 2 (dashed)
  // "leave under another purpose" → chip 3
  const timelineChip1Op = fade(t, 8.14, 8.7);
  const timelineChip2Op = fade(t, 8.7, 9.2);
  const timelineChip3Op = fade(t, 9.2, 9.7);
  const timelineArcOp = fade(t, 9.0, 10.0, 14.0, 15.0);
  
  // Phase 4: Shared device links - SEQUENTIAL per account (10-14s)
  const deviceLink1Op = fade(t, 10.2, 10.7);
  const deviceLink2Op = fade(t, 10.7, 11.2);
  const deviceLink3Op = fade(t, 11.2, 11.7);
  const deviceNodeOp = fade(t, 11.5, 12.2, 16.5, 17.2);
  const deviceLabelOp = fade(t, 12.0, 12.8, 16.5, 17.2);
  
  // Phase 5: Queue cutaway with camera push (12-16s)
  const queueOp = fade(t, 11.8, 12.5, 16.5, 17.2);
  const queuePush = interpolate(t, [11.8, 12.35, 12.35, 14.5], [0.72, 0.85, 0.85, 0.85], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });
  
  // Phase 6: Alert card + ghosts (15-19.6s)
  const alertOp = fade(t, 14.8, 15.5);
  const ghostsOp = fade(t, 15.2, 16.0);
  const cardPulse = 1;

  const wireY = CY + drift * 0.3;
  const thresholdY = wireY - 72;

  return (
    <AbsoluteFill>
      <Background />

      <div
        style={{
          position: "absolute",
          top: 0,
          left: scanX,
          width: 160,
          height: STAGE_BOTTOM,
          background: `linear-gradient(90deg, transparent, ${colors.tealSoft}, transparent)`,
          opacity: 0.4 * (1 - alertOp * 0.5),
          zIndex: 1,
          pointerEvents: "none",
        }}
      />

      {/* Hero explainer — single wire + rule threshold (0–4 s) */}
      <svg
        width={1920}
        height={STAGE_BOTTOM}
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          zIndex: 2,
          transform: `scale(${camPush}) translateY(${camPan}px)`,
          transformOrigin: "50% 45%",
        }}
      >
        <g opacity={ruleOp * (1 - alertOp * 0.85)}>
          <line
            x1={CX - 420}
            y1={wireY}
            x2={CX + 420}
            y2={wireY}
            stroke={colors.brand}
            strokeWidth={5}
            strokeLinecap="round"
            strokeOpacity={0.85}
          />
          <circle cx={CX - 420} cy={wireY} r={14} fill={colors.card} stroke={colors.brand} strokeWidth={3} />
          <circle cx={CX + 420} cy={wireY} r={14} fill={colors.card} stroke={colors.brand} strokeWidth={3} />
          <line
            x1={CX - 480}
            y1={thresholdY}
            x2={CX + 480}
            y2={thresholdY}
            stroke={colors.amber}
            strokeWidth={2}
            strokeDasharray="10 8"
            strokeDashoffset={-dash}
            strokeOpacity={0.75}
          />
          <text
            x={CX + 500}
            y={thresholdY + 6}
            fill={colors.amber}
            fontSize={20}
            fontWeight={600}
            fontFamily="Inter, ui-sans-serif, system-ui, sans-serif"
          >
            rule threshold
          </text>
          <text
            x={CX}
            y={wireY + 44}
            textAnchor="middle"
            fill={colors.inkSecondary}
            fontSize={22}
            fontWeight={600}
            fontFamily="Inter, ui-sans-serif, system-ui, sans-serif"
          >
            one transaction · one wire
          </text>
        </g>

        {/* Rings fan from wire (4-12s) — each ring enters sequentially */}
        <g opacity={ringsOp * (1 - alertOp * 0.7)}>
          {Array.from({ length: ringCount }, (_, i) => {
            const angle = -0.55 + i * 0.37;
            const len = 180 + i * 40 + ringPulse * 12;
            const x2 = CX + Math.cos(angle) * len;
            const y2 = wireY + Math.sin(angle) * len * 0.55;
            const ringDelay = 4.5 + i * 0.4;
            const ringOn = fade(t, ringDelay, ringDelay + 0.5);
            return (
              <line
                key={i}
                x1={CX}
                y1={wireY}
                x2={CX + (x2 - CX) * ringOn}
                y2={wireY + (y2 - wireY) * ringOn}
                stroke={colors.teal}
                strokeWidth={2.5}
                strokeOpacity={0.55 + i * 0.1}
                strokeLinecap="round"
              />
            );
          })}
          <text
            x={CX}
            y={wireY - 100}
            textAnchor="middle"
            fill={colors.ink}
            fontSize={26}
            fontWeight={700}
            fontFamily="Inter, ui-sans-serif, system-ui, sans-serif"
            opacity={fade(t, 4.5, 5.2) * (1 - fade(t, 11.5, 12.2))}
          >
            mule · layering · not one wire
          </text>
        </g>

        {/* Timeline strip — THREE SEQUENTIAL CHIPS per VO clause (8-12s) */}
        <g opacity={timelineArcOp}>
          {/* Connecting arc draws progressively */}
          <path
            d={`M ${CX - 340} ${CY + 148} Q ${CX} ${CY + 100} ${CX + 380} ${CY + 148}`}
            fill="none"
            stroke={colors.inkTertiary}
            strokeWidth={2}
            strokeDasharray="6 6"
            strokeDashoffset={-dash * 0.5}
            opacity={0.6}
          />
          {/* Arc draw animation */}
          <path
            d={`M ${CX - 340} ${CY + 148} Q ${CX} ${CY + 100} ${CX + 380} ${CY + 148}`}
            fill="none"
            stroke={colors.teal}
            strokeWidth={3}
            strokeLinecap="round"
            strokeDasharray="800"
            strokeDashoffset={800 * (1 - interpolate(t, [8.5, 11.0], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: enter }))}
            opacity={0.7}
          />
          
          <TimelineChip
            x={CX - 340}
            y={CY + 120}
            title="CW-MID-01"
            sub="$9,200 · IN→SG · 14:10"
            accent={colors.brand}
            t={t}
            delay={8.14}
            opacity={timelineChip1Op}
          />
          <TimelineChip
            x={CX + 40}
            y={CY + 120}
            title="rest · 18 min"
            sub="purpose change"
            accent={colors.amber}
            t={t}
            delay={8.7}
            dashed
            opacity={timelineChip2Op}
          />
          <TimelineChip
            x={CX + 380}
            y={CY + 120}
            title="CW-MID-02"
            sub={`$${caseData.amount.toLocaleString()} · SG→PH · 14:28`}
            accent={colors.teal}
            t={t}
            delay={9.2}
            opacity={timelineChip3Op}
          />
        </g>

        {/* Shared device — THREE SEQUENTIAL LINKS per account (10-14s) */}
        <g opacity={deviceNodeOp}>
          {[
            { x: CX - 280, label: "ACC · IN", delay: 10.2, linkOp: deviceLink1Op },
            { x: CX - 40, label: "ACC · SG", delay: 10.7, linkOp: deviceLink2Op },
            { x: CX + 220, label: "ACC · PH", delay: 11.2, linkOp: deviceLink3Op },
          ].map((a, i) => (
            <g key={a.label}>
              <rect
                x={a.x - 56}
                y={CY - 20}
                width={112}
                height={40}
                rx={10}
                fill={colors.card}
                stroke={colors.cardBorder}
                strokeWidth={1}
                opacity={a.linkOp}
              />
              <text
                x={a.x}
                y={CY + 6}
                textAnchor="middle"
                fill={colors.inkSecondary}
                fontSize={16}
                fontWeight={600}
                fontFamily="Inter, ui-sans-serif, system-ui, sans-serif"
                opacity={a.linkOp}
              >
                {a.label}
              </text>
              <line
                x1={a.x}
                y1={CY + 24}
                x2={a.x + (CX - a.x) * a.linkOp}
                y2={CY + 24 + (CY + 200 - (CY + 24)) * a.linkOp}
                stroke={colors.teal}
                strokeWidth={2.5}
                strokeLinecap="round"
                strokeOpacity={a.linkOp}
                strokeDasharray={100}
                strokeDashoffset={100 * (1 - a.linkOp)}
              />
            </g>
          ))}
          <circle 
            cx={CX} 
            cy={CY + 200} 
            r={22} 
            fill={colors.tealSoft} 
            stroke={colors.teal} 
            strokeWidth={3}
            opacity={deviceNodeOp}
            filter="url(#nodeShadow)"
          />
          <text
            x={CX}
            y={CY + 248}
            textAnchor="middle"
            fill={colors.tealText}
            fontSize={22}
            fontWeight={800}
            fontFamily="IBM Plex Mono, ui-monospace, monospace"
            opacity={deviceLabelOp}
          >
            {caseData.mule}
          </text>
          <text
            x={CX}
            y={CY + 278}
            textAnchor="middle"
            fill={colors.inkSecondary}
            fontSize={18}
            fontWeight={600}
            fontFamily="Inter, ui-sans-serif, system-ui, sans-serif"
            opacity={deviceLabelOp}
          >
            threshold cannot see this link
          </text>
        </g>

        {/* Ghost unknowns — continuous drift + label pulse (ongoing) */}
        <defs>
          <filter id="nodeShadow" x="-50%" y="-50%" width="200%" height="200%">
            <feDropShadow dx="0" dy="1" stdDeviation="2" flood-color="#0B1220" flood-opacity="0.1" />
          </filter>
        </defs>
        {[
          { x: CX - 520, y: CY - 160 },
          { x: CX + 120, y: CY - 200 },
          { x: CX + 520, y: CY - 120 },
          { x: CX + 560, y: CY + 80 },
        ].map((u, i) => {
          const ghostDrX = 0;
          const ghostDrY = 0;
          const labelPulse = 1;
          return (
            <g key={i} opacity={ghostsOp}>
              <circle
                cx={u.x + ghostDrX}
                cy={u.y + ghostDrY}
                r={11}
                fill="none"
                stroke={colors.unknown}
                strokeWidth={1.5}
                strokeDasharray="4 5"
                strokeDashoffset={t * 20}
              />
              <text
                x={u.x + ghostDrX}
                y={u.y + ghostDrY - 16}
                textAnchor="middle"
                fill={colors.unknown}
                fontSize={15}
                fontWeight={600}
                fontFamily="Inter, ui-sans-serif, system-ui, sans-serif"
                opacity={labelPulse}
              >
                unknown
              </text>
            </g>
          );
        })}
      </svg>

      {/* Queue cutaway — camera pushes in (12-16s) */}
      <AbsoluteFill style={{ opacity: queueOp, zIndex: 4 }}>
        <div
          style={{
            position: "absolute",
            right: safe.x - 20,
            top: safe.y + 40,
            transform: `scale(${queuePush})`,
            transformOrigin: "top right",
          }}
        >
          <DeviceFrame src="captures/queue/queue.jpg" widthPx={920} heightPx={518} scale={1} />
        </div>
      </AbsoluteFill>

      {/* Closing alert card (15-19.6s) */}
      <div
        style={{
          position: "absolute",
          left: "50%",
          top: CY - 80,
          transform: `translate(-50%, 0) scale(${0.94 + alertOp * 0.06 * cardPulse})`,
          width: 480,
          padding: "28px 32px",
          borderRadius: radius.card,
          background: colors.card,
          border: `2px solid ${colors.amber}`,
          boxShadow: shadow.card,
          opacity: alertOp,
          zIndex: 6,
          fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
        }}
      >
        <div
          style={{
            fontSize: 14,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            color: colors.amber,
            fontWeight: 700,
            marginBottom: 10,
          }}
        >
          Alert · risk {caseData.risk}
        </div>
        <div style={{ fontSize: 36, fontWeight: 800, color: colors.ink, letterSpacing: "-0.02em" }}>
          ${caseData.amount.toLocaleString()} · {caseData.corridor}
        </div>
        <div style={{ marginTop: 10, fontSize: 18, color: colors.inkSecondary, fontWeight: 500 }}>
          {caseData.id} · no memory of the network
        </div>
      </div>

      {/* Progress bar — continuous motion */}
      <div
        style={{
          position: "absolute",
          left: safe.x,
          right: safe.x,
          bottom: safe.captionBand + 8,
          height: 3,
          borderRadius: 99,
          background: colors.grid,
          zIndex: 1,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${Math.min(100, (t / DUR) * 100)}%`,
            height: "100%",
            background: colors.brand,
            opacity: 0.35,
          }}
        />
      </div>
    </AbsoluteFill>
  );
};

const TimelineChip: React.FC<{
  x: number;
  y: number;
  title: string;
  sub: string;
  accent: string;
  t: number;
  delay: number;
  dashed?: boolean;
  opacity?: number;
}> = ({ x, y, title, sub, accent, t, delay, dashed, opacity = 1 }) => {
  const on = interpolate(t, [delay, delay + 0.45], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });
  return (
    <g transform={`translate(${x}, ${y})`} opacity={on * opacity}>
      <rect
        x={-120}
        y={-36}
        width={240}
        height={72}
        rx={14}
        fill={colors.card}
        stroke={dashed ? colors.amber : colors.cardBorder}
        strokeWidth={dashed ? 2 : 1}
        strokeDasharray={dashed ? "8 6" : undefined}
        filter="url(#nodeShadow)"
      />
      <text
        x={0}
        y={-6}
        textAnchor="middle"
        fill={accent}
        fontSize={18}
        fontWeight={800}
        fontFamily="Inter, ui-sans-serif, system-ui, sans-serif"
      >
        {title}
      </text>
      <text
        x={0}
        y={22}
        textAnchor="middle"
        fill={colors.inkSecondary}
        fontSize={15}
        fontWeight={600}
        fontFamily="IBM Plex Mono, ui-monospace, monospace"
      >
        {sub}
      </text>
    </g>
  );
};
