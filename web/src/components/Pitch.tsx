import type { MatchEvent } from "../contracts";
import { PITCH_LENGTH_M as L, PITCH_WIDTH_M as W } from "../contracts";
import type { Team } from "../shared";

const TOUCHES = 5; // passes and dribbles of the current possession shown
const HOLD_SECONDS = 30; // match seconds a possession stays drawn after its last touch
const MARK_SECONDS = 30; // presses and tackles
const SHOT_SECONDS = 60;

type Props = { events: MatchEvent[]; t: number; home: Team; away: Team };

/** The current possession as players on the ball (shirt numbers), passes (solid) and dribbles (dashed), with
 *  the ball at the end of the last touch; the other side's presses and tackles as crosses; recent shots as
 *  lines to goal. Events are stored in each team's own frame; the home team attacks right, the away team left. */
export function Pitch({ events, t, home, away }: Props) {
  const team = (id?: string | null) => (id === home.id ? home : away);
  const at = (id: string | null | undefined, x: number, y: number) => (id === home.id ? [x, y] : [L - x, W - y]);
  const shown = events.filter((e) => e.x != null && e.t <= t);
  const touches = shown.filter((e) => e.type === "pass" || e.type === "carry");
  const last = touches.at(-1);
  const live = last && t - last.t < HOLD_SECONDS ? last : undefined;
  const thread = live ? touches.filter((e) => e.sequence_id === live.sequence_id).slice(-TOUCHES) : [];
  const marks = shown.filter((e) => (e.type === "pressure" || e.type === "tackle") && t - e.t < MARK_SECONDS);
  const shots = shown.filter((e) => e.type === "shot" && t - e.t < SHOT_SECONDS);
  const shirt = (e: MatchEvent) => Number(e.player?.split("_").at(-1));
  const fade = (i: number) => 0.35 + (0.65 * (i + 1)) / thread.length;
  const ball = live?.outcome === "complete" ? at(live.team, live.end_x!, live.end_y!) : undefined;
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
      {shots.map((e) => {
        const [x, y] = at(e.team, e.x!, e.y!);
        return (
          <line key={e.id} x1={x} y1={y} x2={e.team === home.id ? L : 0} y2={W / 2} stroke={team(e.team).colors[0]}
            strokeWidth={0.25 + (e.xg ?? 0) * 1.5} strokeLinecap="round" opacity={1 - (t - e.t) / SHOT_SECONDS} />
        );
      })}
      {marks.map((e) => {
        const [x, y] = at(e.team, e.x!, e.y!);
        return (
          <g key={e.id} stroke={team(e.team).colors[0]} strokeWidth=".5" strokeLinecap="round" opacity={1 - (t - e.t) / MARK_SECONDS}>
            <line x1={x - 1} y1={y - 1} x2={x + 1} y2={y + 1} />
            <line x1={x + 1} y1={y - 1} x2={x - 1} y2={y + 1} />
          </g>
        );
      })}
      {thread.map((e, i) => {
        const [x1, y1] = at(e.team, e.x!, e.y!);
        const [x2, y2] = at(e.team, e.end_x!, e.end_y!);
        return (
          <line key={e.id} x1={x1} y1={y1} x2={x2} y2={y2} stroke={team(e.team).colors[0]} strokeWidth=".55"
            strokeLinecap="round" strokeDasharray={e.type === "carry" ? "1.2 1" : undefined} opacity={fade(i)} />
        );
      })}
      {thread.map((e, i) => {
        const [x, y] = at(e.team, e.x!, e.y!);
        const { colors } = team(e.team);
        const onBall = i === thread.length - 1;
        return (
          <g key={e.id} opacity={fade(i)}>
            <circle cx={x} cy={y} r={onBall ? 2.2 : 1.9} fill={colors[0]} stroke={colors[1]} strokeWidth=".3" />
            <text x={x} y={y + 0.8} fontSize="2.2" fontWeight="600" textAnchor="middle" fill={colors[1]}>{shirt(e)}</text>
            {onBall && (
              // Below the dot near the top edge, where the scorebug would cover it.
              <text x={x} y={y < 12 ? y + 4.8 : y - 3.2} fontSize="2.2" textAnchor="middle" fill="var(--bar)">
                {team(e.team).squad[shirt(e) - 1]}
              </text>
            )}
          </g>
        );
      })}
      {ball && <circle cx={ball[0]} cy={ball[1]} r=".9" fill="var(--bar)" stroke="var(--ink)" strokeWidth=".25" />}
    </svg>
  );
}
