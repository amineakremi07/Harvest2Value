"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { Badge, Card, cx, ErrorBanner, Loading, PageHeader } from "@/components/ui/primitives";
import { API_ORIGIN, errorMessage } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import { useApi } from "@/lib/hooks/useApi";
import type { ThemeChoice } from "@/lib/theme/theme";
import { useTheme } from "@/lib/theme/useTheme";

const THEMES: { value: ThemeChoice; label: string; icon: typeof Sun }[] = [
  { value: "light", label: "Clair", icon: Sun },
  { value: "dark", label: "Sombre", icon: Moon },
  { value: "system", label: "Système", icon: Monitor },
];

export default function SettingsPage() {
  const meta = useApi(() => api.meta(), []);
  const { choice, setChoice } = useTheme();
  return (
    <>
      <PageHeader title="Réglages" />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card title="API">
          {meta.loading ? (
            <Loading />
          ) : meta.error || !meta.data ? (
            <ErrorBanner message={errorMessage(meta.error)} onRetry={meta.reload} />
          ) : (
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
              <dt className="text-slate-400">Adresse</dt>
              <dd className="break-all font-mono text-slate-200">{API_ORIGIN}</dd>
              <dt className="text-slate-400">Version</dt>
              <dd className="text-slate-200">
                {meta.data.app_version} ({meta.data.environment})
              </dd>
              <dt className="text-slate-400">LLM</dt>
              <dd className="text-slate-200">
                {meta.data.llm.provider} · {meta.data.llm.model}{" "}
                <Badge tone={meta.data.llm.configured ? "success" : "warning"}>{meta.data.llm.configured ? "configuré" : "IA désactivée"}</Badge>
              </dd>
              <dt className="text-slate-400">Limite solveur</dt>
              <dd className="text-slate-200">{meta.data.limits.solver_time_limit_s} s</dd>
            </dl>
          )}
        </Card>
        <Card title="Apparence">
          <fieldset>
            <legend className="mb-3 text-sm text-slate-400">Thème de l&apos;interface (mémorisé dans ce navigateur).</legend>
            <div className="flex flex-wrap gap-2">
              {THEMES.map(({ value, label, icon: Icon }) => (
                <label
                  key={value}
                  className={cx(
                    "inline-flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm font-semibold has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-cyan-accent",
                    choice === value ? "border-emerald-accent text-white" : "border-card-border text-slate-300 hover:border-slate-500",
                  )}
                >
                  <input type="radio" name="theme" value={value} checked={choice === value} onChange={() => setChoice(value)} className="sr-only" />
                  <Icon className="h-4 w-4" aria-hidden="true" />
                  {label}
                </label>
              ))}
            </div>
          </fieldset>
        </Card>
      </div>
    </>
  );
}
