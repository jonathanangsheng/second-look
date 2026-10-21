import type { MatchEvent } from "./contracts";
import { PITCH_LENGTH_M as L, PITCH_WIDTH_M as W } from "./contracts";

const DOT_SECONDS = 30; // match seconds a dot takes to fade (3s of wall clock at 10x)
const SHOT_SECONDS = 60;
const DRAWN = new Set(["pass", "carry", "shot", "tackle", "pressure"]);

type Props = { events: MatchEvent[]; t: number; homeId: string; colors: Record<string, string> };

/** Events are stored in each team's own frame; the home team attacks right, the away team left. */
export function Pitch({ events, t, homeId, colors }: Props) {
  const recent = events.filter((e) => e.x != null && DRAWN.has(e.type) && e.t <= t && t - e.t < SHOT_SECONDS);
  const at = (e: MatchEvent) => (e.team === homeId ? [e.x!, e.y!] : [L - e.x!, W - e.y!]);
  return (
    <svg className="pitch" viewBox={`0 0 ${L} ${W}`} role="img" aria-label="Pitch replay">
      <rect width={L} height={W} fill="var(--turf)" />
      <g fill="none" stroke="var(--turf-line)" strokeWidth=".3">
        <rect x=".5" y=".5" width={L - 1} height={W - 1} />
        <line x1={L / 2} y1=".5" x2={L / 2} y2={W - 0.5} />
        <circle cx={L / 2} cy={W / 2} r="9.15" />
        <rect x=".5" y="13.84" width="16.5" height="40.32" />
        <rect x={L - 17} y="13.84" width="16.5" height="40.32" />
      </g>
      {recent.map((e) => {
        const [x, y] = at(e);
        const fill = colors[e.team];
        if (e.type === "shot") {
          const goalX = e.team === homeId ? L : 0;
          return (
            <line key={e.id} x1={x} y1={y} x2={goalX} y2={W / 2} stroke={fill}
              strokeWidth={0.25 + (e.xg ?? 0) * 1.5} strokeLinecap="round" opacity={1 - (t - e.t) / SHOT_SECONDS} />
          );
        }
        if (t - e.t >= DOT_SECONDS) return null;
        return <circle key={e.id} cx={x} cy={y} r=".9" fill={fill} stroke="var(--ink)" strokeWidth=".15" opacity={1 - (t - e.t) / DOT_SECONDS} />;
      })}
    </svg>
  );
}
