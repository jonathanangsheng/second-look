import { useCallback, useEffect, useState } from "react";
import { LowerThird } from "./components/LowerThird";
import { OutcomeCard } from "./components/OutcomeCard";
import { Pitch } from "./components/Pitch";
import type { CacheMode, Card, Lang, MatchEvent, Persona } from "./contracts";
import { type Meta, SPEAKERS, type Team, verdictText } from "./shared";
import { FULL_TIME, usePlayback } from "./usePlayback";

const SHOW_FOR = 60; // match seconds a card stays up once its hold ends
const SPEEDS = [1, 10, 30];

async function getJSON<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json();
}

const cardKey = (c: Card) => `${c.seed}-${c.window}-${c.kind}`;
const ordinal = (n: number) => `${n}${["th", "st", "nd", "rd"][n % 100 >= 11 && n % 100 <= 13 ? 0 : Math.min(n % 10, 4) % 4] ?? "th"}`;

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [seed, setSeed] = useState("demo");
  const [mode, setMode] = useState<CacheMode>("normal");
  const [events, setEvents] = useState<MatchEvent[]>([]);
  const [cards, setCards] = useState<Card[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [persona, setPersona] = useState<Persona>("casual");
  const [club, setClub] = useState<string | null>(null); // the team the viewer supports, if any
  const [lang, setLang] = useState<Lang>("en");
  const [chip, setChip] = useState(0);
  const { t, setT, playing, speed, setSpeed, instant, seek, togglePlay, stop } = usePlayback(cards);

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
  }, [setT]);

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

  const goChip = async (i: number) => {
    const c = meta?.chips[i];
    if (!c) return;
    stop();
    setChip(i);
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
  const supporting = match && (club === match.home.id || club === match.away.id) ? club : null; // stale after a match switch
  const live = (pick: (c: Card) => boolean) =>
    [...cards].reverse().find((c) => pick(c) && c.t_start <= t && t < c.t_start + SHOW_FOR);
  const debate = live((c) => c.kind === "debate");
  const outcome = live((c) => c.kind !== "debate");
  const minute = Math.floor(t / 60);
  const goals = (team?: Team) => events.filter((e) => e.type === "goal" && e.team === team?.id && e.t <= t).length;
  const dir = lang === "ar" ? "rtl" : "ltr";

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
              {match && (
                <div role="group" aria-label="Supporting">
                  <button aria-pressed={supporting === null} onClick={() => setClub(null)}>Neutral</button>
                  {[match.home, match.away].map((team) => (
                    <button key={team.id} aria-pressed={supporting === team.id} onClick={() => setClub(team.id)}>{team.short}</button>
                  ))}
                </div>
              )}
              <div role="group" aria-label="Language">
                {(["en", "es", "ar"] as const).map((l) => (
                  <button key={l} aria-pressed={lang === l} onClick={() => setLang(l)}>{l.toUpperCase()}</button>
                ))}
              </div>
            </div>
          </header>

          <main className={`picture ${status === "loading" ? "dim" : ""}`}>
            {match && <Pitch events={events} t={t} home={match.home} away={match.away} />}
            <ul className="pitch-legend" aria-label="Pitch key">
              <li><svg viewBox="0 0 10 10" aria-hidden="true"><circle cx="5" cy="5" r="4" fill="var(--bar)" /></svg>Player on the ball</li>
              <li><svg viewBox="0 0 16 10" aria-hidden="true"><line x1="1" y1="5" x2="15" y2="5" /></svg>Pass</li>
              <li><svg viewBox="0 0 16 10" aria-hidden="true"><line x1="1" y1="5" x2="15" y2="5" strokeDasharray="3 2" /></svg>Dribble</li>
              <li><svg viewBox="0 0 10 10" aria-hidden="true"><path d="M2 2l6 6M8 2l-6 6" /></svg>Press, tackle</li>
              <li><svg viewBox="0 0 16 10" aria-hidden="true"><line x1="1" y1="5" x2="15" y2="5" strokeWidth="3" /></svg>Shot, thicker = better chance</li>
            </ul>
            {match && (
              <div className="scorebug" aria-label="Score">
                <span className="num clock">{t >= FULL_TIME ? "FT" : `${minute}'`}</span>
                <span className="team">{match.home.short}</span>
                <span className="num score">
                  {[match.home, match.away].map((team) => (
                    <span key={team.id} style={{ background: team.colors[0], color: team.colors[1] }}>{goals(team)}</span>
                  ))}
                </span>
                <span className="team">{match.away.short}</span>
              </div>
            )}
            {outcome && <OutcomeCard key={cardKey(outcome)} card={outcome} lang={lang} dir={dir} instant={instant} />}
            <div className="slot" dir={dir} lang={lang}>
              {status === "error" ? (
                <div className="lower-third message">
                  <p>Couldn't load this match.</p>
                  <button onClick={() => void (meta ? load(seed, mode, t) : boot())}>Retry</button>
                </div>
              ) : status === "loading" ? (
                <div className="lower-third message"><p>Loading match…</p></div>
              ) : debate ? (
                <LowerThird key={cardKey(debate)} card={debate} persona={persona} club={supporting} lang={lang} instant={instant} events={events} match={match!} t={t} />
              ) : null}
            </div>
            <div className="sr-only" aria-live="polite" lang={lang}>
              {debate ? SPEAKERS.map(([s, label]) => `${label}: ${s === "verdict" ? verdictText(debate, persona, supporting, lang) : debate.lines[s]?.[lang]}`).join(" ") : ""}
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
