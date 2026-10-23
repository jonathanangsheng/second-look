import type { Card, Lang } from "../contracts";
import { withBdi } from "../shared";

type Props = { card: Card; lang: Lang; dir: string; instant: boolean };

export function OutcomeCard({ card, lang, dir, instant }: Props) {
  const made = card.evidence_display?.made_at_minute?.[lang] ?? "";
  const claim = card.evidence_display?.claim?.[lang];
  const hit = card.kind === "called_it";
  return (
    <aside className={`outcome ${instant ? "instant" : ""}`} dir={dir} lang={lang}>
      {claim && <p className="quote">{withBdi(`${made} — ${claim}`, lang)}</p>}
      <p className="result">
        <span className={`mark ${hit ? "hit" : "miss"}`} aria-hidden="true" />
        <span className="label">{hit ? "Called it" : "Missed"}</span>
        <span>{withBdi(card.lines.verdict?.[lang] ?? "", lang)}</span>
      </p>
    </aside>
  );
}
