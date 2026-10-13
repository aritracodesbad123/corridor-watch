import React from "react";
import { AbsoluteFill, Audio, Composition, Series, staticFile } from "remotion";
import { fps, height, width } from "./design/tokens";
import { MASTER_DURATION_S, SCENES, secToFrame } from "./audio/voClock";
import { S00_Hook } from "./scenes/S00_Hook";
import { S01_TheGap } from "./scenes/S01_TheGap";
import { S02_Brand } from "./scenes/S02_Brand";
import { S03_Triage } from "./scenes/S03_Triage";
import { S04_Evidence } from "./scenes/S04_Evidence";
import { S05_Corridor } from "./scenes/S05_Corridor";
import { S06_Grounded } from "./scenes/S06_Grounded";
import { S07_Human } from "./scenes/S07_Human";
import { S08_PatternDNA } from "./scenes/S08_PatternDNA";
import { S09_Outro } from "./scenes/S09_Outro";
import { First10s } from "./scenes/First10s";
import { Pass2DagSlice } from "./scenes/Pass2DagSlice";

const SCENE_COMPONENTS: Record<string, React.FC> = {
  S00: S00_Hook,
  S01: S01_TheGap,
  S02: S02_Brand,
  S03: S03_Triage,
  S04: S04_Evidence,
  S05: S05_Corridor,
  S06: S06_Grounded,
  S07: S07_Human,
  S08: S08_PatternDNA,
  S09: S09_Outro,
};

function sceneDurationFrames(s: (typeof SCENES)[number]): number {
  const end = (s as { picture_end?: number }).picture_end ?? s.vo_end;
  return Math.max(1, secToFrame(end - s.vo_start, fps));
}

/** Picture-only series (audio muxed in post for reliable ducking). */
export const MasterPicture: React.FC = () => (
  <Series>
    {SCENES.map((s) => {
      const Comp = SCENE_COMPONENTS[s.id] ?? S00_Hook;
      return (
        <Series.Sequence key={s.id} durationInFrames={sceneDurationFrames(s)}>
          <Comp />
        </Series.Sequence>
      );
    })}
  </Series>
);

export const MasterFilm: React.FC = () => (
  <AbsoluteFill>
    <Audio src={staticFile("audio/voiceover.wav")} />
    <MasterPicture />
  </AbsoluteFill>
);

const MASTER_FRAMES = secToFrame(MASTER_DURATION_S, fps);

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="First10s"
        component={First10s}
        durationInFrames={10 * fps}
        fps={fps}
        width={width}
        height={height}
      />
      <Composition
        id="Pass2DagSlice"
        component={Pass2DagSlice}
        durationInFrames={15 * fps}
        fps={fps}
        width={width}
        height={height}
      />
      <Composition
        id="Master"
        component={MasterFilm}
        durationInFrames={MASTER_FRAMES}
        fps={fps}
        width={width}
        height={height}
      />
      <Composition
        id="MasterPicture"
        component={MasterPicture}
        durationInFrames={MASTER_FRAMES}
        fps={fps}
        width={width}
        height={height}
      />
      {SCENES.map((s) => {
        const Comp = SCENE_COMPONENTS[s.id] ?? S00_Hook;
        return (
          <Composition
            key={s.id}
            id={`Scene-${s.id}`}
            component={Comp}
            durationInFrames={sceneDurationFrames(s)}
            fps={fps}
            width={width}
            height={height}
          />
        );
      })}
    </>
  );
};
