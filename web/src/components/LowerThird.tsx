import type { Card, Lang, MatchEvent, Persona } from "../contracts";
import { type Match, SPEAKERS, withBdi } from "../shared";
import { EvidenceRow } from "./EvidenceRow";

const BADGE: Record<string, [string, string] | undefined> = {
  template: ["Backup text", "badge-grey"],
  cache: ["Agent failed, backup used", "badge-amber"],
};

type Props = { card: Card; persona: Persona; lang: Lang; instant: boolean; events: MatchEvent[]; match: Match; t: number };

export function LowerThird({ card, persona, lang, instant, events, match, t }: Props) {
  return (
    <>
      <div className={`lower-third ${instant ? "instant" : ""}`}>
        {SPEAKERS.map(([s, label], i) => {
          const verdict = s === "verdict";
          const text = verdict ? card.variants[persona][lang] : card.lines[s]?.[lang];
          const badge = BADGE[(verdict ? card.source.personaliser : card.source[s]) ?? "live"];
          return (
            <div key={s} className={`line ${s}`} style={{ animationDelay: `${i * 1.2}s` }}>
              <span className="speaker">{label}</span>
              <span className="text">
                {withBdi(text ?? "", lang)}
                {verdict && card.window_from_minute != null && <span className="tag">Since <bdi>{card.window_from_minute}'</bdi></span>}
              </span>
              {badge && <span className={`badge ${badge[1]}`}>{badge[0]}</span>}
            </div>
          );
        })}
      </div>
      {persona === "analyst" && <EvidenceRow card={card} lang={lang} events={events} match={match} t={t} />}
    </>
  );
}
