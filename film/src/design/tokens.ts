/** Pass-2 premium light theme (Stripe/Linear-light). Product primary ≈ #2763E8. */
export const colors = {
  canvas: "#F4F7FB",
  canvasHi: "#FFFFFF",
  canvasLo: "#E6EEF9",
  blobBlue: "rgba(39,99,232,0.08)",
  blobTeal: "rgba(31,158,142,0.10)",
  ink: "#0B1220",
  inkSecondary: "#3B4658",
  inkTertiary: "#6B7686",
  brand: "#2763E8",
  brandSoft: "rgba(39,99,232,0.12)",
  teal: "#1F9E8E",
  tealText: "#0F7F72",
  tealSoft: "rgba(31,158,142,0.16)",
  amber: "#C87010",
  amberTint: "#FDF5EB",
  critical: "#D6404F",
  criticalTint: "#FDECEE",
  positive: "#1E9E6A",
  card: "#FFFFFF",
  cardBorder: "rgba(11,18,32,0.08)",
  grid: "rgba(11,18,32,0.06)",
  unknown: "#8A97A8",
  // legacy aliases used by existing scenes (map to light)
  bg0: "#F4F7FB",
  bg1: "#FFFFFF",
  glowInner: "#E6EEF9",
  glowOuter: "#F4F7FB",
  tealGlow: "rgba(31,158,142,0.25)",
  text: "#0B1220",
  text70: "rgba(11,18,32,0.70)",
  text45: "rgba(11,18,32,0.45)",
  glass: "rgba(255,255,255,0.92)",
  glassBorder: "rgba(11,18,32,0.08)",
} as const;

export const type = {
  eyebrow: 22,
  headline: 72,
  subhead: 36,
  caption: 36,
  min: 22,
} as const;

/** 1080p safe: 96 L/R, 72 top; caption band = bottom 140px (y 940–1080). */
export const safe = { x: 96, y: 72, captionBand: 140 } as const;

export const radius = { card: 18, pill: 12 } as const;

export const shadow = {
  card: "0 1px 2px rgba(11,18,32,0.06), 0 12px 32px rgba(11,18,32,0.08), 0 40px 80px rgba(11,18,32,0.10)",
  device: "0 8px 24px rgba(11,18,32,0.10), 0 40px 80px rgba(11,18,32,0.12)",
} as const;

export const fps = 30;
export const width = 1920;
export const height = 1080;
