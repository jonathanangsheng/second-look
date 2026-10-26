import type { Card, Lang, MatchEvent } from "../contracts";
import { FULL_TIME_MINUTE } from "../contracts";
import { type Match, withBdi } from "../shared";
import { Sparkline } from "./Sparkline";

type Props = { card: Card; lang: Lang; events: MatchEvent[]; match: Match; t: number };

const WORDS = {
  en: { shots: "Shots", perShot: "xG/shot", threshold: "Threshold", gap: "Gap", possession: "Possession", entries: "Box entries", vs: "vs", ratio: "Ratio", pressing: "Pressing", behind: "behind", before: "before" },
  es: { shots: "Tiros", perShot: "xG/tiro", threshold: "Umbral", gap: "Diferencia", possession: "Posesión", entries: "Entradas al área", vs: "vs", ratio: "Ratio", pressing: "Presión", behind: "perdiendo", before: "antes" },
  ar: { shots: "التسديدات", perShot: "xG/تسديدة", threshold: "الحد", gap: "الفارق", possession: "الاستحواذ", entries: "دخول المنطقة", vs: "مقابل", ratio: "النسبة", pressing: "الضغط", behind: "متأخراً بالنتيجة", before: "قبل ذلك" },
} satisfies Record<Lang, Record<string, string>>;

export function EvidenceRow({ card, lang, events, match, t }: Props) {
  const d = (key: string) => card.evidence_display?.[key]?.[lang] ?? "";
  const w = WORDS[lang];
  const cells = {
    volume_quality: [`${w.shots} ${d("shots")}`, `${w.perShot} ${d("xg_per_shot")}`, `${w.threshold} ${d("threshold")}`],
    scoreline_xg: [`${d("trailer")} xG ${d("trailer_xg_window")}`, `${d("leader")} xG ${d("leader_xg_window")}`, `${w.gap} ≥ ${d("threshold")}`],
    possession_penetration: [
      `${w.possession} ${d("possession_pct")}`,
      `${w.entries} ${d("box_entry_rate")} ${w.vs} ${d("opponent_box_entry_rate")}`,
      `${w.ratio} ${d("ratio")} < ${d("max_ratio")}`,
    ],
    effort_game_state: [
      `${w.pressing} ${d("press_rate_while_behind")} ${w.behind}`,
      `${d("press_rate_while_level")} ${w.before}`,
      `${w.ratio} ${d("ratio")} < ${d("max_ratio")}`,
    ],
  }[card.detector];
  return (
    <div className="evidence">
      {cells.map((c) => <span key={c} className="num">{withBdi(c, lang)}</span>)}
      {card.detector === "scoreline_xg" && <Sparkline events={events} match={match} upTo={Math.min(FULL_TIME_MINUTE, Math.floor(t / 60))} />}
    </div>
  );
}
