import type { Card, Lang } from "../contracts";
import { withBdi } from "../shared";

type Props = { card: Card; lang: Lang; dir: string; instant: boolean };

const RESULT = {
  en: { hit: "Called it", miss: "Missed" },
  es: { hit: "Acertó", miss: "Falló" },
  ar: { hit: "توقع صائب", miss: "توقع خاطئ" },
} satisfies Record<Lang, Record<string, string>>;

export function OutcomeCard({ card, lang, dir, instant }: Props) {
  const made = card.evidence_display?.made_at_minute?.[lang] ?? "";
  const claim = card.claim?.[lang];
  const hit = card.kind === "called_it";
  return (
    <aside className={`outcome ${instant ? "instant" : ""}`} dir={dir} lang={lang}>
      {claim && <p className="quote">{withBdi(`${made} — ${claim}`, lang)}</p>}
      <p className="result">
        <span className={`mark ${hit ? "hit" : "miss"}`} aria-hidden="true" />
        <span className="label">{RESULT[lang][hit ? "hit" : "miss"]}</span>
        <span>{withBdi(card.lines.verdict?.[lang] ?? "", lang)}</span>
      </p>
    </aside>
  );
}
