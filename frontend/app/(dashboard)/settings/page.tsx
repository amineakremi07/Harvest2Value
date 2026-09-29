"use client";

import { useState, type FormEvent } from "react";
import { Check } from "lucide-react";
import PageTitle from "@/app/components/PageTitle";
import { glassCard, inputClass } from "@/app/components/styles";
import {
  DATE_RANGES,
  useDelegation,
  type DateRangeKey,
} from "@/app/context/DelegationProvider";
import { useAgent } from "@/app/lib/auth";

const label = "mb-1 block text-xs font-semibold text-text-secondary";

const NOTIFICATIONS = [
  { id: "critical-storage", label: "Storage facility reaches 90% capacity" },
  { id: "waste-spike", label: "Waste rises versus the previous period" },
  { id: "weekly-digest", label: "Weekly regional summary email" },
] as const;

export default function SettingsPage() {
  const { delegations, selected, selectDelegation, dateRange, setDateRange } = useDelegation();
  const agent = useAgent();
  const [notify, setNotify] = useState<Record<string, boolean>>({
    "critical-storage": true,
    "waste-spike": true,
    "weekly-digest": false,
  });
  const [saved, setSaved] = useState(false);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaved(true);
  }

  return (
    <>
      <PageTitle title="Settings" subtitle="Delegation preferences and account configuration." />

      <form onSubmit={handleSubmit} className="grid gap-4 lg:grid-cols-2">
        <section aria-labelledby="prefs-title" className={glassCard}>
          <h2 id="prefs-title" className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
            Delegation preferences
          </h2>
          <div className="space-y-4">
            <div>
              <label htmlFor="pref-delegation" className={label}>Active delegation</label>
              <select
                id="pref-delegation"
                value={selected.id}
                onChange={(e) => {
                  selectDelegation(e.target.value);
                  setSaved(false);
                }}
                className={inputClass}
              >
                {delegations.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} — {d.governorate}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="pref-range" className={label}>Default date range</label>
              <select
                id="pref-range"
                value={dateRange}
                onChange={(e) => {
                  setDateRange(e.target.value as DateRangeKey);
                  setSaved(false);
                }}
                className={inputClass}
              >
                {DATE_RANGES.map((r) => (
                  <option key={r.key} value={r.key}>
                    {r.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </section>

        <section aria-labelledby="account-title" className={glassCard}>
          <h2 id="account-title" className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
            Account
          </h2>
          <dl className="space-y-3 text-sm">
            <div>
              <dt className="text-xs font-semibold text-text-secondary">Official email</dt>
              <dd className="font-mono text-text-primary">{agent?.email ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-text-secondary">Delegation ID</dt>
              <dd className="font-mono text-text-primary">{agent?.delegationId ?? "—"}</dd>
            </div>
          </dl>
        </section>

        <fieldset className={`${glassCard} lg:col-span-2`}>
          <legend className="px-1 text-sm font-semibold uppercase tracking-wider text-text-secondary">
            Notifications
          </legend>
          <div className="mt-3 space-y-3">
            {NOTIFICATIONS.map((n) => (
              <label key={n.id} className="flex cursor-pointer items-center gap-3 text-sm text-text-primary">
                <input
                  type="checkbox"
                  checked={notify[n.id]}
                  onChange={(e) => {
                    setNotify((prev) => ({ ...prev, [n.id]: e.target.checked }));
                    setSaved(false);
                  }}
                  className="h-4 w-4 accent-[var(--accent)]"
                />
                {n.label}
              </label>
            ))}
          </div>
        </fieldset>

        <div className="flex flex-wrap items-center gap-3 lg:col-span-2">
          <button
            type="submit"
            className="inline-flex min-h-[44px] items-center rounded-full bg-accent px-6 py-2.5 text-sm font-bold text-white outline-none transition-colors hover:bg-accent-hover focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-bg"
          >
            Save preferences
          </button>
          {saved && (
            <span role="status" className="inline-flex items-center gap-1.5 text-sm font-semibold text-success">
              <Check className="h-4 w-4" aria-hidden="true" /> Saved for this session
            </span>
          )}
        </div>
      </form>
    </>
  );
}
