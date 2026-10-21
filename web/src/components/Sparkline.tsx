import type { MatchEvent } from "../contracts";
import { FULL_TIME_MINUTE } from "../contracts";
import type { Match } from "../shared";

/** Rolling 30-minute xG per minute for both teams, with a half-time tick. */
export function Sparkline({ events, match, upTo }: { events: MatchEvent[]; match: Match; upTo: number }) {
  const shots = events.filter((e) => e.type === "shot");
  const series = [match.home, match.away].map((team) =>
    Array.from({ length: upTo + 1 }, (_, m) =>
      shots.filter((s) => s.team === team.id && s.minute < m && s.minute >= m - 30).reduce((a, s) => a + (s.xg ?? 0), 0)));
  const top = Math.max(1, ...series.flat());
  const x = (m: number) => (m / FULL_TIME_MINUTE) * 160;
  return (
    <svg className="spark" width="160" height="24" viewBox="0 0 160 24" aria-label="Rolling 30-minute xG for both teams">
      <line x1={x(45)} y1="0" x2={x(45)} y2="24" stroke="var(--grey-badge)" strokeWidth="1" />
      {series.map((pts, i) => (
        <polyline key={i} fill="none" strokeWidth="1.5" stroke={[match.home, match.away][i].colors[0]}
          points={pts.map((v, m) => `${x(m).toFixed(1)},${(22 - (v / top) * 20).toFixed(1)}`).join(" ")} />
      ))}
    </svg>
  );
}
