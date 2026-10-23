// Mirror of src/second_look/contracts.py. Change both, plus tests/fixtures, in one commit.

export type Lang = "en" | "es" | "ar";
export type Persona = "analyst" | "casual";
export type Speaker = "hype" | "sceptic" | "verdict";
export type Source = "live" | "cache" | "template";
export type CacheMode = "normal" | "fail-sceptic";

export type EventType =
  | "pass" | "carry" | "shot" | "pressure" | "tackle"
  | "possession_start" | "possession_end" | "goal" | "period";

export type Outcome =
  | "complete" | "incomplete" | "saved" | "blocked" | "off_target" | "goal" | "won" | "lost";

export type Detector =
  | "volume_quality" | "possession_penetration" | "scoreline_xg" | "effort_game_state";

export const PITCH_LENGTH_M = 105;
export const PITCH_WIDTH_M = 68;
export const FULL_TIME_MINUTE = 90;

export interface MatchEvent {
  id: number;
  t: number; // seconds since kick-off
  minute: number;
  period: 1 | 2;
  type: EventType;
  team: string;
  player?: string | null;
  sequence_id?: number | null;
  x?: number | null; // metres, attacking left to right for `team`
  y?: number | null;
  end_x?: number | null; // required for pass and carry
  end_y?: number | null;
  outcome?: Outcome | null;
  xg?: number | null; // required for shot
}

export interface StatValue {
  label: string;
  value: number;
}

export type LangText = Record<Lang, string>;
export type Evidence = Record<string, number | string>;

export interface Contradiction {
  id: string;
  detector: Detector;
  team: string;
  minute: number;
  surface: StatValue;
  truth: StatValue;
  evidence: Evidence;
  evidence_display: Record<string, LangText>;
  severity: number; // 0..1
  prediction_id?: string | null;
  window_from_minute?: number | null; // shown as "Since 30'"
}

export interface Prediction {
  id: string;
  team: string; // the trailing team, ahead on xG
  event_type: "goal";
  made_at_minute: number;
  by_minute: number; // min(made_at + 25, 90)
  claim_text: string;
  status: "open" | "fulfilled" | "expired";
}

export interface Card {
  seed: string;
  window: number;
  t_start: number;
  t_end: number;
  kind: "debate" | "called_it" | "missed_call";
  detector: Detector; // outcome cards carry their call's detector, scoreline_xg
  contradiction_id?: string | null;
  prediction_id?: string | null;
  window_from_minute?: number | null;
  claim?: LangText | null; // the prediction, on a call's debate card and its outcome card
  lines: Partial<Record<Speaker, LangText>>;
  // The Verdict line on screen is variants[persona][lang]; Hype and Sceptic never change.
  variants: Record<Persona, LangText>;
  source: Partial<Record<"hype" | "sceptic" | "verdict" | "personaliser" | "es" | "ar", Source>>;
  evidence: Evidence;
  evidence_display?: Record<string, LangText>;
}

// A debate and an outcome card can share a window, so the kind is part of the file name.
export function cardPath(seed: string, mode: CacheMode, window: number, kind: Card["kind"]): string {
  return `${seed}/${mode}/${String(window).padStart(2, "0")}-${kind}.json`;
}
