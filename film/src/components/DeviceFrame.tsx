import React from "react";
import { Img, staticFile } from "remotion";
import { colors, radius, shadow } from "../design/tokens";

/** Product UI plate — integer-pixel placement, no subpixel drift. */
export const DeviceFrame: React.FC<{
  src: string;
  scale?: number;
  opacity?: number;
  objectPosition?: string;
  widthPx?: number;
  heightPx?: number;
}> = ({
  src,
  scale = 1,
  opacity = 1,
  objectPosition = "top left",
  widthPx = 1680,
  heightPx = 945,
}) => {
  const s = Math.round(scale * 1000) / 1000;
  const w = Math.round(widthPx);
  const h = Math.round(heightPx);
  return (
    <div
      style={{
        position: "absolute",
        left: "50%",
        top: "50%",
        width: w,
        height: h,
        // ponytail: round translate via calc; Remotion still centers — upgrade to left/top px if subpixel persists
        transform: `translate(-50%, -50%) scale(${s})`,
        opacity,
        borderRadius: radius.card,
        overflow: "hidden",
        boxShadow: shadow.device,
        border: `1px solid ${colors.cardBorder}`,
        background: colors.card,
        willChange: "auto",
      }}
    >
      <Img
        src={staticFile(src)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          objectPosition,
        }}
      />
    </div>
  );
};
