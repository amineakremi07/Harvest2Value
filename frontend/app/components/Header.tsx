"use client";

import { CloudSun, Sun, Wind, type LucideIcon } from "lucide-react";
import {
  DATE_RANGES,
  useDelegation,
  type DateRangeKey,
} from "@/app/context/DelegationProvider";

const CONTROL_CLASS =
  "rounded-xl border border-card-border bg-card-surface px-3 py-2 text-sm text-text-primary " +
  "outline-none transition-colors hover:border-accent/50 focus-visible:ring-2 focus-visible:ring-accent";

/** Sample conditions per delegation until a weather endpoint exists. */
const MOCK_WEATHER: Record<string, { tempC: number; label: string; icon: LucideIcon }> = {
  mornag: { tempC: 24, label: "Sunny", icon: Sun },
  tebourba: { tempC: 22, label: "Partly cloudy", icon: CloudSun },
  kelibia: { tempC: 21, label: "Windy", icon: Wind },
};

export default function Header() {
  const { delegations, selected, selectDelegation, dateRange, setDateRange } = useDelegation();
  const weather = MOCK_WEATHER[selected.id];
  const WeatherIcon = weather?.icon;

  // pr-14 keeps controls clear of the fixed top-right theme toggle (layout.tsx).
  return (
    <header className="flex flex-wrap items-center gap-3 border-b border-card-border bg-app-bg py-4 pr-14">
      <div className="mr-auto min-w-[12rem]">
        <p className="text-xl font-bold text-text-primary">Harvest2Value - CRDA</p>
        <p className="text-sm text-text-secondary">
          Regional harvest, storage and farmer analytics for {selected.name}.
        </p>
      </div>

      <input
        type="search"
        aria-label="Search farmers, delegations, crops"
        placeholder="Search farmers, delegations, crops..."
        className={`${CONTROL_CLASS} w-full placeholder:text-text-secondary sm:w-64`}
      />

      {weather && WeatherIcon && (
        <div
          className="flex items-center gap-2 rounded-xl border border-card-border bg-card-surface px-3 py-2 text-sm text-text-primary"
          title="Sample weather data"
        >
          <WeatherIcon className="h-4 w-4 text-warning" aria-hidden="true" />
          <span className="font-mono tabular-nums">{weather.tempC}°C</span>
          <span>{weather.label}</span>
          <span className="text-text-secondary">• {selected.name}</span>
        </div>
      )}

      <label className="flex items-center gap-2 text-xs font-medium text-text-secondary">
        <span>Delegation</span>
        <select
          value={selected.id}
          onChange={(e) => selectDelegation(e.target.value)}
          className={`${CONTROL_CLASS} font-semibold`}
        >
          {delegations.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
      </label>

      <label className="flex items-center gap-2 text-xs font-medium text-text-secondary">
        <span className="sr-only">Date range</span>
        <select
          value={dateRange}
          onChange={(e) => setDateRange(e.target.value as DateRangeKey)}
          className={CONTROL_CLASS}
        >
          {DATE_RANGES.map((r) => (
            <option key={r.key} value={r.key}>
              {r.label}
            </option>
          ))}
        </select>
      </label>
    </header>
  );
}
