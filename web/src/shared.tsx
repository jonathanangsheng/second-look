import type { ReactNode } from "react";
import type { CacheMode, Card, Lang, Persona, Speaker } from "./contracts";

// squad[n - 1] is the fictional name of player id p_<team>_<n>.
export type Team = { id: string; name: string; short: string; colors: [string, string]; squad: string[] };
type Chip = { label: string; seed: string; mode: CacheMode; t: number; minute: number };
export type Match = { seed: string; home: Team; away: Team };
export type Meta = { seeds: Match[]; chips: Chip[] };

export const SPEAKERS = [["hype", "Hype agent"], ["sceptic", "Sceptic agent"], ["verdict", "Verdict agent"]] as const satisfies readonly (readonly [Speaker, string])[];

/** Arabic text: keep numbers in left-to-right order inside right-to-left lines. */
export function withBdi(text: string, lang: Lang): ReactNode {
  if (lang !== "ar") return text;
  return text.split(/(\d+(?:[.,]\d+)?'?)/).map((part, i) => (i % 2 ? <bdi key={i}>{part}</bdi> : part));
}

/** The Verdict as shown: a supporter's fan line when the card has one for their team, else the persona's line. */
export function verdictText(card: Card, persona: Persona, club: string | null, lang: Lang): string {
  return ((club && card.fans?.[club]) || card.variants[persona])[lang];
}
