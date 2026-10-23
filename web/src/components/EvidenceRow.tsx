import type { Card, Lang, MatchEvent } from "../contracts";
import { FULL_TIME_MINUTE } from "../contracts";
import { type Match, withBdi } from "../shared";
import { Sparkline } from "./Sparkline";

type Props = { card: Card; lang: Lang; events: MatchEvent[]; match: Match; t: number };

export function EvidenceRow({ card, lang, events, match, t }: Props) {
  const d = (key: string) => card.evidence_display?.[key]?.[lang] ?? "";
  const cells = card.detector === "volume_quality"
    ? [`Shots ${d("shots")}`, `xG/shot ${d("xg_per_shot")}`, `Threshold ${d("threshold")}`]
    : [`${d("trailer")} xG ${d("trailer_xg_window")}`, `${d("leader")} xG ${d("leader_xg_window")}`, `Gap ≥ ${d("threshold")}`];
  return (
    <div className="evidence">
      {cells.map((c) => <span key={c} className="num">{withBdi(c, lang)}</span>)}
      {card.detector === "scoreline_xg" && <Sparkline events={events} match={match} upTo={Math.min(FULL_TIME_MINUTE, Math.floor(t / 60))} />}
    </div>
  );
}
