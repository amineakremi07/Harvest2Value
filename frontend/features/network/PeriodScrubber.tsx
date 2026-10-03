"use client";

import { useEffect, useId, useState } from "react";
import { ChevronLeft, ChevronRight, Pause, Play } from "lucide-react";
import { Button } from "@/components/ui/primitives";

/** Picks one day of the horizon, or the whole period (`null`); can play through the days. */
export function PeriodScrubber({
  horizon,
  day,
  onChange,
  intervalMs = 1200,
}: {
  horizon: number;
  day: number | null;
  onChange: (day: number | null) => void;
  intervalMs?: number;
}) {
  const id = useId();
  const [playing, setPlaying] = useState(false);
  const last = Math.max(0, horizon - 1);

  useEffect(() => {
    if (!playing) return;
    const timer = setInterval(() => {
      onChange(day === null || day >= last ? 0 : day + 1);
    }, intervalMs);
    return () => clearInterval(timer);
  }, [playing, day, last, onChange, intervalMs]);

  const step = (delta: number) => {
    setPlaying(false);
    const current = day ?? 0;
    onChange(Math.min(last, Math.max(0, current + delta)));
  };

  return (
    <div className="flex flex-wrap items-center gap-3" role="group" aria-label="Période affichée">
      <label className="flex items-center gap-2 text-sm text-slate-300">
        <input
          type="checkbox"
          checked={day === null}
          onChange={(e) => {
            setPlaying(false);
            onChange(e.target.checked ? null : 0);
          }}
        />
        Toute la période
      </label>
      <Button variant="ghost" aria-label="Jour précédent" onClick={() => step(-1)} disabled={day === 0}>
        <ChevronLeft className="h-4 w-4" aria-hidden="true" />
      </Button>
      <input
        id={id}
        type="range"
        min={0}
        max={last}
        value={day ?? 0}
        aria-label="Jour"
        aria-valuetext={day === null ? "Toute la période" : `Jour ${day}`}
        className="w-48 accent-emerald-500"
        onChange={(e) => {
          setPlaying(false);
          onChange(Number(e.target.value));
        }}
      />
      <Button variant="ghost" aria-label="Jour suivant" onClick={() => step(1)} disabled={day === last}>
        <ChevronRight className="h-4 w-4" aria-hidden="true" />
      </Button>
      <Button variant="ghost" aria-label={playing ? "Pause" : "Lecture"} onClick={() => setPlaying((p) => !p)}>
        {playing ? <Pause className="h-4 w-4" aria-hidden="true" /> : <Play className="h-4 w-4" aria-hidden="true" />}
      </Button>
      <output htmlFor={id} className="min-w-24 font-mono text-sm text-white">
        {day === null ? `J0 – J${last}` : `Jour ${day}`}
      </output>
    </div>
  );
}
