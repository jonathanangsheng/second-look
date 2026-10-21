import { useEffect, useRef, useState } from "react";
import type { Card } from "./contracts";
import { FULL_TIME_MINUTE } from "./contracts";

export const FULL_TIME = FULL_TIME_MINUTE * 60;
const HOLD_MS = 7000; // max(7s, reveal 2.65s + 3s)

/** The match clock: plays at `speed` match-seconds per second and pauses for HOLD_MS whenever a card starts. */
export function usePlayback(cards: Card[]) {
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(10);
  const [instant, setInstant] = useState(true); // landing shows the debate fully revealed
  const holdUntil = useRef(0);
  const tRef = useRef(0);
  tRef.current = t;

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
  /** Pause, drop any hold and let the next card animate in (before jumping to a chip). */
  const stop = () => {
    setPlaying(false);
    holdUntil.current = 0;
    setInstant(false);
  };

  return { t, setT, playing, speed, setSpeed, instant, seek, togglePlay, stop };
}
