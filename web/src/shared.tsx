import type { ReactNode } from "react";
import type { CacheMode, Lang, Speaker } from "./contracts";

export type Team = { id: string; name: string; short: string; colors: [string, string] };
type Chip = { label: string; seed: string; mode: CacheMode; t: number; minute: number };
export type Match = { seed: string; home: Team; away: Team };
export type Meta = { seeds: Match[]; chips: Chip[] };

export const SPEAKERS = [["hype", "Hype agent"], ["sceptic", "Sceptic agent"], ["verdict", "Verdict agent"]] as const satisfies readonly (readonly [Speaker, string])[];

/** Arabic text: keep numbers in left-to-right order inside right-to-left lines. */
export function withBdi(text: string, lang: Lang): ReactNode {
  if (lang !== "ar") return text;
  return text.split(/(\d+(?:[.,]\d+)?'?)/).map((part, i) => (i % 2 ? <bdi key={i}>{part}</bdi> : part));
}
