import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { Background } from "../components/Background";
import { colors, radius, safe, shadow, type as typeScale } from "../design/tokens";
import { enter, holdBreath } from "../motion/easing";
import { fade, useLocalSec } from "../motion/useLocalSec";

/** S09 — picture to 220 s (VO ends 212.2). ~16.62 s local from 203.38. */
export const S09_Outro: React.FC = () => {
  const t = useLocalSec();
  const frame = Math.round(t * 60);

  const logoBuild = fade(t, 0.2, 1.4);
  const logoLetters = fade(t, 0.4, 2.0);

  const tag1 = fade(t, 3.0, 4.2);
  const tag2 = fade(t, 4.4, 5.8);
  const tag3 = fade(t, 6.0, 7.6);

  const ctaIn = fade(t, 8.0, 9.2);
  const urlIn = fade(t, 9.4, 10.4);
  const synthIn = fade(t, 10.6, 11.6);

  const breathe = holdBreath(frame, 200);
  const push = interpolate(t, [0, 0.55, 0.55, 16.62], [1.0, 1.02, 1.02, 1.02], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: enter,
  });
  const ctaPulse = 1;
  const logoShimmer = 0;

  return (
    <AbsoluteFill>
      <Background />

      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          transform: `scale(${push})`,
          zIndex: 2,
          paddingBottom: safe.captionBand * 0.35,
        }}
      >
        <div style={{ textAlign: "center", maxWidth: 1200, padding: "0 48px", position: "relative" }}>
          <div
            style={{
              position: "relative",
              display: "inline-block",
              marginBottom: 32,
              opacity: logoBuild,
              transform: `scale(${0.88 + 0.12 * logoBuild})`,
            }}
          >
            <div
              style={{
                fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
                fontSize: 88,
                fontWeight: 800,
                letterSpacing: "-0.03em",
                color: colors.ink,
                lineHeight: 1,
              }}
            >
              {"Corridor Watch".split("").map((ch, i) => (
                <span
                  key={i}
                  style={{
                    display: "inline-block",
                    opacity: ch === " " ? 1 : fade(t, 0.35 + i * 0.06, 0.55 + i * 0.06),
                    transform: `translateY(${(1 - logoLetters) * 18}px)`,
                  }}
                >
                  {ch === " " ? "\u00a0" : ch}
                </span>
              ))}
            </div>
            <div
              style={{
                position: "absolute",
                inset: -8,
                background: `linear-gradient(105deg, transparent ${logoShimmer * 100}%, rgba(255,255,255,0.55) ${logoShimmer * 100 + 8}%, transparent ${logoShimmer * 100 + 16}%)`,
                mixBlendMode: "soft-light",
                pointerEvents: "none",
                opacity: 0.7 * logoBuild,
              }}
            />
          </div>

          <div
            style={{
              fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
              fontSize: typeScale.subhead,
              fontWeight: 500,
              color: colors.inkSecondary,
              lineHeight: 1.45,
              maxWidth: 980,
              margin: "0 auto 36px",
            }}
          >
            <div
              style={{
                opacity: tag1,
                transform: `translateY(${(1 - tag1) * 12}px)`,
                marginBottom: 8,
              }}
            >
              The transaction is not the crime.
            </div>
            <div
              style={{
                opacity: tag2,
                transform: `translateY(${(1 - tag2) * 12}px)`,
                marginBottom: 8,
                fontWeight: 600,
                color: colors.ink,
              }}
            >
              The network is.
            </div>
            <div
              style={{
                opacity: tag3,
                transform: `translateY(${(1 - tag3) * 12}px)`,
                color: colors.brand,
                fontWeight: 600,
              }}
            >
              Corridor Watch turns investigations into institutional memory.
            </div>
          </div>

          <div
            style={{
              transform: `scale(${ctaPulse})`,
              opacity: ctaIn,
              marginBottom: 18,
            }}
          >
            <div
              style={{
                display: "inline-block",
                padding: "16px 36px",
                borderRadius: radius.pill,
                background: colors.brand,
                color: colors.canvasHi,
                fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
                fontSize: 26,
                fontWeight: 700,
                boxShadow: shadow.card,
                letterSpacing: "-0.01em",
              }}
            >
              Book a walkthrough
            </div>
          </div>

          <div
            style={{
              fontFamily: "IBM Plex Mono, ui-monospace, monospace",
              fontSize: 22,
              fontWeight: 500,
              color: colors.tealText,
              opacity: urlIn,
              transform: `translateY(${(1 - urlIn) * 8}px)`,
              marginBottom: 8,
            }}
          >
            corridor.watch
          </div>
        </div>
      </AbsoluteFill>

      <div
        style={{
          position: "absolute",
          left: safe.x,
          right: safe.x,
          bottom: safe.y,
          textAlign: "center",
          fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
          fontSize: 16,
          color: colors.text45,
          opacity: synthIn * (0.85 + 0.15 * breathe),
          zIndex: 3,
        }}
      >
        Synthetic demo data
      </div>
    </AbsoluteFill>
  );
};
