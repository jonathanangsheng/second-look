import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import type { CacheMode, Card, Lang, MatchEvent, Persona } from "./contracts";
import { FULL_TIME_MINUTE } from "./contracts";
import { Pitch } from "./Pitch";

type Team = { id: string; name: string; short: string; colors: [string, string] };
type Chip = { label: string; seed: string; mode: CacheMode; t: number; minute: number };
type Meta = { seeds: { seed: string; home: Team; away: Team }[]; chips: Chip[] };

const FULL_TIME = FULL_TIME_MINUTE * 60;
const SHOW_FOR = 60; // match seconds a card stays up once its hold ends
const HOLD_MS = 7000; // max(7s, reveal 2.65s + 3s)
const SPEEDS = [1, 10, 30];
const SPEAKERS = [["hype", "Hype agent"], ["sceptic", "Sceptic agent"], ["verdict", "Verdict agent"]] as const;
const BADGE: Record<string, [string, string] | undefined> = {
  template: ["Backup text", "badge-grey"],
  cache: ["Agent failed, backup used", "badge-amber"],
};

async function getJSON<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json();
}

const cardKey = (c: Card) => `${c.seed}-${c.window}-${c.kind}`;
const detector = (c: Card) => (c.contradiction_id ?? "").includes("_scoreline_xg_") ? "scoreline_xg" : "volume_quality";
const ordinal = (n: number) => `${n}${["th", "st", "nd", "rd"][n % 100 >= 11 && n % 100 <= 13 ? 0 : Math.min(n % 10, 4) % 4] ?? "th"}`;

/** Arabic text: keep numbers in left-to-right order inside right-to-left lines. */
function withBdi(text: string, lang: Lang): ReactNode {
  if (lang !== "ar") return text;
  return text.split(/(\d+(?:[.,]\d+)?'?)/).map((part, i) => (i % 2 ? <bdi key={i}>{part}</bdi> : part));
}

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [seed, setSeed] = useState("demo");
  const [mode, setMode] = useState<CacheMode>("normal");
  const [events, setEvents] = useState<MatchEvent[]>([]);
  const [cards, setCards] = useState<Card[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(10);
  const [persona, setPersona] = useState<Persona>("casual");
  const [lang, setLang] = useState<Lang>("en");
  const [chip, setChip] = useState(0);
  const [instant, setInstant] = useState(true); // landing shows the debate fully revealed
  const holdUntil = useRef(0);
  const tRef = useRef(0);
  tRef.current = t;

  const load = useCallback(async (s: string, m: CacheMode, at: number) => {
    setStatus("loading");
    try {
      const [ev, cs] = await Promise.all([
        getJSON<MatchEvent[]>(`/api/match/${s}/events`),
        getJSON<Card[]>(`/api/match/${s}/cards?mode=${m}`),
      ]);
      setEvents(ev);
      setCards(cs);
      setSeed(s);
      setMode(m);
      setT(at);
      setStatus("ready");
    } catch {
      setStatus("error");
    }
  }, []);

  const boot = useCallback(async () => {
    setStatus("loading");
    try {
      const body = await getJSON<Meta>("/api/seeds");
      setMeta(body);
      const first = body.chips[0];
      await load(first?.seed ?? "demo", first?.mode ?? "normal", first?.t ?? 0);
    } catch {
      setStatus("error");
    }
  }, [load]);

  useEffect(() => void boot(), [boot]);

  // Fit the 1280x720 frame to the window (desktop); the stacked layout ignores --scale.
  useEffect(() => {
    const fit = () => document.documentElement.style.setProperty("--scale", String(Math.min(innerWidth / 1280, (innerHeight - 32) / 720)));
    fit();
    addEventListener("resize", fit);
    return () => removeEventListener("resize", fit);
  }, []);

  // Playback: the clock pauses for HOLD_MS whenever a card starts.
  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      if (now >= holdUntil.current) {
        const prev = tRef.current;
        const next = Math.min(FULL_TIME, prev + dt * speed);
        const started = cards.find((c) => c.t_start > prev && c.t_start <= next);
        if (started) {
          holdUntil.current = now + HOLD_MS;
          setInstant(false);
          setT(started.t_start);
        } else {
          setT(next);
          if (next >= FULL_TIME) setPlaying(false);
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed, cards]);

  const seek = (to: number) => {
    holdUntil.current = 0;
    setInstant(false);
    setT(Math.max(0, Math.min(FULL_TIME, to)));
  };
  const togglePlay = () => {
    holdUntil.current = 0;
    if (!playing && t >= FULL_TIME) setT(0);
    setPlaying(!playing);
  };
  const goChip = async (i: number) => {
    const c = meta?.chips[i];
    if (!c) return;
    setPlaying(false);
    holdUntil.current = 0;
    setChip(i);
    setInstant(false);
    if (c.seed !== seed || c.mode !== mode) await load(c.seed, c.mode, c.t);
    else setT(c.t);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const inRange = e.target instanceof HTMLInputElement;
      if (e.key === " " && !(e.target instanceof HTMLButtonElement)) {
        e.preventDefault();
        togglePlay();
      } else if (!inRange && e.key === "ArrowLeft") seek(t - 60);
      else if (!inRange && e.key === "ArrowRight") seek(t + 60);
      else if (/^[1-5]$/.test(e.key)) void goChip(Number(e.key) - 1);
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  });

  const match = meta?.seeds.find((s) => s.seed === seed);
  const live = (pick: (c: Card) => boolean) =>
    [...cards].reverse().find((c) => pick(c) && c.t_start <= t && t < c.t_start + SHOW_FOR);
  const debate = live((c) => c.kind === "debate");
  const outcome = live((c) => c.kind !== "debate");
  const minute = Math.floor(t / 60);
  const goals = (team?: Team) => events.filter((e) => e.type === "goal" && e.team === team?.id && e.t <= t).length;
  const dir = lang === "ar" ? "rtl" : "ltr";
  const colors = match ? { [match.home.id]: match.home.colors[0], [match.away.id]: match.away.colors[0] } : {};

  return (
    <div className="stage">
      <div className="frame-box">
        <div className="frame">
          <header className="strip">
            <p className="headline">The stat on screen is lying.</p>
            <nav className="chips" aria-label="Key moments">
              {meta?.chips.map((c, i) => (
                <button key={c.label} className="chip" aria-pressed={i === chip && c.seed === seed} onClick={() => void goChip(i)}>
                  {c.seed === "demo" && <span className="num">{c.minute}'</span>} {c.label}
                </button>
              ))}
            </nav>
            <div className="toggles">
              <div role="group" aria-label="Audience">
                {(["analyst", "casual"] as const).map((p) => (
                  <button key={p} aria-pressed={persona === p} onClick={() => setPersona(p)}>{p === "analyst" ? "Analyst" : "Casual"}</button>
                ))}
              </div>
              <div role="group" aria-label="Language">
                {(["en", "es", "ar"] as const).map((l) => (
                  <button key={l} aria-pressed={lang === l} onClick={() => setLang(l)}>{l.toUpperCase()}</button>
                ))}
              </div>
            </div>
          </header>

          <main className={`picture ${status === "loading" ? "dim" : ""}`}>
            <Pitch events={events} t={t} homeId={match?.home.id ?? ""} colors={colors} />
            {match && (
              <div className="scorebug" aria-label="Score">
                <span className="swatch" style={{ background: match.home.colors[0] }} />
                <span>{match.home.short}</span>
                <span className="num score">{goals(match.home)}-{goals(match.away)}</span>
                <span>{match.away.short}</span>
                <span className="swatch" style={{ background: match.away.colors[0] }} />
                <span className="num clock">{t >= FULL_TIME ? "FT" : `${minute}'`}</span>
              </div>
            )}
            {outcome && <OutcomeCard key={cardKey(outcome)} card={outcome} cards={cards} lang={lang} dir={dir} instant={instant} />}
            <div className="slot" dir={dir} lang={lang}>
              {status === "error" ? (
                <div className="lower-third message">
                  <p>Couldn't load this match.</p>
                  <button onClick={() => void (meta ? load(seed, mode, t) : boot())}>Retry</button>
                </div>
              ) : status === "loading" ? (
                <div className="lower-third message"><p>Loading match…</p></div>
              ) : debate ? (
                <LowerThird key={cardKey(debate)} card={debate} persona={persona} lang={lang} instant={instant} events={events} match={match!} t={t} />
              ) : null}
            </div>
            <div className="sr-only" aria-live="polite" lang={lang}>
              {debate ? SPEAKERS.map(([s, label]) => `${label}: ${s === "verdict" ? debate.variants[persona][lang] : debate.lines[s]?.[lang]}`).join(" ") : ""}
            </div>
          </main>

          <div className="timeline">
            <button className="play" onClick={togglePlay} aria-label={playing ? "Pause" : "Play"}>{playing ? "❚❚" : "▶"}</button>
            <div role="group" aria-label="Speed" className="speeds">
              {SPEEDS.map((s) => (
                <button key={s} aria-pressed={speed === s} onClick={() => setSpeed(s)}>{s}x</button>
              ))}
            </div>
            <input type="range" min={0} max={FULL_TIME} step={1} value={t} aria-label="Match time"
              aria-valuetext={`${ordinal(minute)} minute`} onChange={(e) => seek(Number(e.target.value))} />
            <span className="pill">Replay</span>
          </div>
        </div>
      </div>
      <footer className="disclaimer">Fictional teams inspired by public playing-style analysis. Not affiliated with or endorsed by the Premier League or any club.</footer>
    </div>
  );
}

type LowerProps = { card: Card; persona: Persona; lang: Lang; instant: boolean; events: MatchEvent[]; match: Meta["seeds"][number]; t: number };

function LowerThird({ card, persona, lang, instant, events, match, t }: LowerProps) {
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

function EvidenceRow({ card, lang, events, match, t }: Omit<LowerProps, "persona" | "instant">) {
  const d = (key: string) => card.evidence_display?.[key]?.[lang] ?? "";
  const cells = detector(card) === "volume_quality"
    ? [`Shots ${d("shots")}`, `xG/shot ${d("xg_per_shot")}`, `Threshold ${d("threshold")}`]
    : [`${d("team")} xG ${d("trailer_xg_window")}`, `${d("leader")} xG ${d("leader_xg_window")}`, `Gap ≥ ${d("threshold")}`];
  return (
    <div className="evidence">
      {cells.map((c) => <span key={c} className="num">{withBdi(c, lang)}</span>)}
      {detector(card) === "scoreline_xg" && <Sparkline events={events} match={match} upTo={Math.min(FULL_TIME_MINUTE, Math.floor(t / 60))} />}
    </div>
  );
}

/** Rolling 30-minute xG per minute for both teams, with a half-time tick. */
function Sparkline({ events, match, upTo }: { events: MatchEvent[]; match: Meta["seeds"][number]; upTo: number }) {
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

function OutcomeCard({ card, cards, lang, dir, instant }: { card: Card; cards: Card[]; lang: Lang; dir: string; instant: boolean }) {
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
