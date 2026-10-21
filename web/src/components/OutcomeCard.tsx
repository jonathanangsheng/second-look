import type { Card, Lang } from "../contracts";
import { withBdi } from "../shared";

type Props = { card: Card; cards: Card[]; lang: Lang; dir: string; instant: boolean };

export function OutcomeCard({ card, cards, lang, dir, instant }: Props) {
  const call = cards.find((c) => c.kind === "debate" && c.prediction_id === card.prediction_id);
  const made = card.evidence_display?.made_at_minute?.[lang] ?? "";
  const hit = card.kind === "called_it";
  return (
    <aside className={`outcome ${instant ? "instant" : ""}`} dir={dir} lang={lang}>
      {call && <p className="quote">{withBdi(`${made} — ${call.lines.verdict?.[lang] ?? ""}`, lang)}</p>}
      <p className="result">
        <span className={`mark ${hit ? "hit" : "miss"}`} aria-hidden="true" />
        <span className="label">{hit ? "Called it" : "Missed"}</span>
        <span>{withBdi(card.lines.verdict?.[lang] ?? "", lang)}</span>
      </p>
    </aside>
  );
}
