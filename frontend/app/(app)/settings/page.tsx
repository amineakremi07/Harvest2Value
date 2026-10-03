"use client";

import Link from "next/link";
import { History } from "lucide-react";
import { Badge, Card, ErrorBanner, Loading, PageHeader } from "@/components/ui/primitives";
import { API_ORIGIN, errorMessage } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import { useApi } from "@/lib/hooks/useApi";

export default function SettingsPage() {
  const meta = useApi(() => api.meta(), []);
  return (
    <>
      <PageHeader title="Réglages" />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="API">
          {meta.loading ? (
            <Loading />
          ) : meta.error || !meta.data ? (
            <ErrorBanner message={errorMessage(meta.error)} onRetry={meta.reload} />
          ) : (
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
              <dt className="text-slate-400">Adresse</dt>
              <dd className="font-mono text-slate-200">{API_ORIGIN}</dd>
              <dt className="text-slate-400">Version</dt>
              <dd className="text-slate-200">
                {meta.data.app_version} ({meta.data.environment})
              </dd>
              <dt className="text-slate-400">LLM</dt>
              <dd className="text-slate-200">
                {meta.data.llm.provider} · {meta.data.llm.model}{" "}
                <Badge tone={meta.data.llm.configured ? "success" : "warning"}>{meta.data.llm.configured ? "configuré" : "non configuré"}</Badge>
              </dd>
              <dt className="text-slate-400">Limite solveur</dt>
              <dd className="text-slate-200">{meta.data.limits.solver_time_limit_s} s</dd>
            </dl>
          )}
        </Card>
        <Card title="Interface">
          <p className="mb-3 text-sm text-slate-400">L&apos;interface V1 reste disponible jusqu&apos;à la fin de la migration.</p>
          <Link
            href="/legacy"
            className="inline-flex items-center gap-2 rounded-lg border border-card-border px-3 py-2 text-sm font-semibold text-slate-200 hover:border-slate-500"
          >
            <History className="h-4 w-4" aria-hidden="true" />
            Ancienne interface
          </Link>
        </Card>
      </div>
    </>
  );
}
