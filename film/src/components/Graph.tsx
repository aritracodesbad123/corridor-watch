import React, { useMemo } from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { colors } from "../design/tokens";
import { enter } from "../motion/easing";

type Node = {
  id: string;
  x: number;
  y: number;
  label: string;
  labelDy: number;
  r: number;
  fill?: string;
  dashed?: boolean;
};

type Edge = {
  a: string;
  b: string;
  dashed?: boolean;
  width?: number;
};

function seeded(i: number): number {
  const x = Math.sin(i * 12.9898 + 78.233) * 43758.5453;
  return x - Math.floor(x);
}

/** Left→right corridor: BANK_IN → BANK_SG → $9,050 → BANK_PH, mule + unknown hop. */
function layout(): { heroes: Node[]; ghosts: Node[]; edges: Edge[] } {
  const y = 540;
  const heroes: Node[] = [
    { id: "in", x: 260, y, label: "BANK_IN", labelDy: -36, r: 16 },
    { id: "sg", x: 620, y, label: "BANK_SG", labelDy: -36, r: 18, fill: colors.teal },
    { id: "pay", x: 980, y, label: "$9,050", labelDy: -36, r: 28, fill: colors.teal },
    { id: "ph", x: 1340, y, label: "BANK_PH", labelDy: -36, r: 16 },
    { id: "dev", x: 1340, y: 780, label: "D-MID-MULE", labelDy: 40, r: 14 },
    {
      id: "hk",
      x: 1680,
      y: 680,
      label: "BANK_HK ?",
      labelDy: 40,
      r: 12,
      dashed: true,
    },
  ];
  const ghosts: Node[] = [];
  for (let i = 0; i < 30; i++) {
    ghosts.push({
      id: `g${i}`,
      x: 200 + seeded(i) * 1520,
      y: 180 + seeded(i + 40) * 720,
      label: "",
      labelDy: 0,
      r: 2 + seeded(i + 7) * 2,
    });
  }
  const edges: Edge[] = [
    { a: "in", b: "sg", width: 4 },
    { a: "sg", b: "pay", width: 4 },
    { a: "pay", b: "ph", width: 4 },
    { a: "ph", b: "dev", width: 3 },
    { a: "ph", b: "hk", width: 2.5, dashed: true },
  ];
  return { heroes, ghosts, edges };
}

export const NetworkGraph: React.FC<{
  start: number;
  showLabels?: boolean;
}> = ({ start, showLabels = true }) => {
  const frame = useCurrentFrame();
  const { heroes, ghosts, edges } = useMemo(() => layout(), []);
  const byId = useMemo(
    () => Object.fromEntries([...heroes, ...ghosts].map((n) => [n.id, n])),
    [heroes, ghosts],
  );

  const progress = interpolate(frame, [start, start + 36], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });
  const scale = 0.92 + 0.08 * progress;

  // Drift for ghost nodes (slow, deterministic)
  const ghostDrift = useMemo(() =>
    ghosts.map((_, i) => ({
      dx: Math.sin(frame * 0.003 + i * 1.7) * 8,
      dy: Math.cos(frame * 0.0025 + i * 2.3) * 5,
    })),
    [frame, ghosts]
  );

  return (
    <svg
      width={1920}
      height={1080}
      style={{
        position: "absolute",
        inset: 0,
        transform: `scale(${scale})`,
        transformOrigin: "50% 50%",
        opacity: progress,
      }}
    >
      <defs>
        <marker
          id="arrow"
          viewBox="0 0 10 10"
          refX={9}
          refY={5}
          markerWidth={7}
          markerHeight={7}
          orient="auto-start-reverse"
        >
          <path d="M 0 0 L 10 5 L 0 10 z" fill={colors.teal} />
        </marker>
        {/* Soft shadow for nodes */}
        <filter id="nodeShadow" x="-50%" y="-50%" width="200%" height="200%">
          <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#0B1220" flood-opacity="0.15" />
        </filter>
      </defs>

      {/* Ghost connections — very subtle, animated */}
      {ghosts.map((n, i) => {
        const m = ghosts[(i + 11) % ghosts.length];
        const drift = ghostDrift[i];
        const driftM = ghostDrift[(i + 11) % ghosts.length];
        return (
          <line
            key={`ge${i}`}
            x1={n.x + drift.dx}
            y1={n.y + drift.dy}
            x2={m.x + driftM.dx}
            y2={m.y + driftM.dy}
            stroke={colors.teal}
            strokeOpacity={0.04 * progress}
            strokeWidth={0.5}
          />
        );
      })}

      {/* Ghost nodes — white fill, teal stroke, soft shadow, slow drift */}
      {ghosts.map((n, i) => {
        const drift = ghostDrift[i];
        return (
          <circle
            key={n.id}
            cx={n.x + drift.dx}
            cy={n.y + drift.dy}
            r={n.r}
            fill={colors.card}
            stroke={colors.teal}
            strokeOpacity={0.25 * progress}
            strokeWidth={1}
            opacity={0.5 * progress}
            filter="url(#nodeShadow)"
          />
        );
      })}

      {/* Spine label */}
      <text
        x={980}
        y={410}
        textAnchor="middle"
        fill={colors.inkTertiary}
        fontSize={20}
        fontWeight={600}
        letterSpacing={2}
        fontFamily="Inter, ui-sans-serif, system-ui, sans-serif"
        opacity={0.8 * progress}
      >
        OBSERVED PATH · SG → PH
      </text>

      {/* Edges — teal, 3-4px, dashed for unknown */}
      {edges.map((e, i) => {
        const A = byId[e.a];
        const B = byId[e.b];
        const draw = interpolate(frame, [start + 8 + i * 7, start + 28 + i * 7], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: enter,
        });
        const dx = B.x - A.x;
        const dy = B.y - A.y;
        const len = Math.hypot(dx, dy) || 1;
        const ux = dx / len;
        const uy = dy / len;
        const x1 = A.x + ux * (A.r + 4);
        const y1 = A.y + uy * (A.r + 4);
        const x2 = B.x - ux * (B.r + 10);
        const y2 = B.y - uy * (B.r + 10);
        const seg = Math.hypot(x2 - x1, y2 - y1);
        const dash = e.dashed ? "10 8" : undefined;
        return (
          <line
            key={`e${i}`}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke={colors.teal}
            strokeOpacity={(e.dashed ? 0.5 : 0.9) * draw}
            strokeWidth={e.width ?? 3.5}
            strokeLinecap="round"
            strokeDasharray={dash ?? `${seg}`}
            strokeDashoffset={dash ? 0 : seg * (1 - draw)}
            markerEnd={e.dashed ? undefined : "url(#arrow)"}
          />
        );
      })}

      {/* Flow particle along spine — white core, teal shadow */}
      {(() => {
        const path = [byId.in, byId.sg, byId.pay, byId.ph];
        const t = ((frame - start) * 0.012) % 1;
        if (t < 0 || progress < 0.25) return null;
        const seg = t * (path.length - 1);
        const i = Math.floor(seg);
        const p = seg - i;
        const A = path[i];
        const B = path[Math.min(i + 1, path.length - 1)];
        return (
          <g filter="url(#nodeShadow)">
            <circle
              cx={A.x + (B.x - A.x) * p}
              cy={A.y + (B.y - A.y) * p}
              r={5}
              fill={colors.card}
              stroke={colors.teal}
              strokeWidth={1.5}
              opacity={0.95 * progress}
            />
            <circle
              cx={A.x + (B.x - A.x) * p}
              cy={A.y + (B.y - A.y) * p}
              r={2}
              fill={colors.teal}
              opacity={0.95 * progress}
            />
          </g>
        );
      })()}

      {/* Hero nodes — solid fill, white ring, soft shadow, labels >= 24px */}
      {heroes.map((n, i) => {
        const appear = interpolate(frame, [start + i * 5, start + 20 + i * 5], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: enter,
        });
        const isFocal = n.id === "pay";
        const nodeR = isFocal ? n.r + 4 : n.r;
        const ringR = nodeR + 4;
        return (
          <g key={n.id} opacity={appear}>
            {/* Soft shadow */}
            <circle
              cx={n.x}
              cy={n.y}
              r={nodeR}
              fill={n.fill ?? colors.card}
              filter="url(#nodeShadow)"
            />
            {/* White ring for depth on light theme */}
            <circle
              cx={n.x}
              cy={n.y}
              r={ringR}
              fill="none"
              stroke={colors.card}
              strokeWidth={3}
              strokeOpacity={0.9}
            />
            {/* Main node */}
            <circle
              cx={n.x}
              cy={n.y}
              r={nodeR}
              fill={n.fill ?? colors.card}
              stroke={colors.teal}
              strokeWidth={isFocal ? 3.5 : 2.5}
              strokeDasharray={n.dashed ? "6 5" : undefined}
            />
            {/* Focal node gets amber alert ring when relevant */}
            {isFocal && (
              <circle
                cx={n.x}
                cy={n.y}
                r={nodeR + 8 + Math.sin(frame * 0.1) * 3}
                fill="none"
                stroke={colors.amber}
                strokeWidth={2}
                strokeOpacity={0.4 + 0.2 * Math.sin(frame * 0.15)}
                strokeDasharray="8 6"
              />
            )}
            {showLabels && (
              <text
                x={n.x}
                y={n.y + n.labelDy}
                textAnchor="middle"
                fill={n.dashed ? colors.inkTertiary : colors.ink}
                fontSize={isFocal ? 32 : 26}
                fontWeight={700}
                fontFamily="Inter, ui-sans-serif, system-ui, sans-serif"
              >
                {n.label}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
};
