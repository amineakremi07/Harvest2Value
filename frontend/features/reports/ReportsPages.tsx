"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Download, FilePlus2, Printer, Trash2 } from "lucide-react";
import { Badge, Button, Card, EmptyState, ErrorBanner, Loading, PageHeader, Table, tdClass, thClass } from "@/components/ui/primitives";
import { errorMessage } from "@/lib/api/client";
import { api, downloads } from "@/lib/api/endpoints";
import { useApi } from "@/lib/hooks/useApi";
import type { ReportSection } from "@/lib/api/types";
import { fmtDate } from "@/lib/format";
import { useAiStatus } from "@/features/copilot/useAiStatus";
import { ReportBuilderForm } from "./ReportBuilderForm";
import { asSnapshot, ReportDocument, SECTION_LABEL } from "./ReportDocument";

const linkButton =
  "inline-flex min-h-9 items-center gap-2 rounded-lg border border-card-border bg-navy-deep px-3 py-1.5 text-sm font-semibold text-slate-200 hover:border-slate-500";

export function ReportsIndex() {
  const reports = useApi(() => api.reports(), []);
  return (
    <>
      <PageHeader
        title="Rapports"
        subtitle="Copies figées d'un plan (et de sa comparaison), imprimables et exportables en CSV ou JSON."
        actions={
          <Link href="/reports/new" className={`${linkButton} border-emerald-500/50 text-emerald-200`}>
            <FilePlus2 className="h-4 w-4" aria-hidden="true" />
            Nouveau rapport
          </Link>
        }
      />
      {reports.loading && !reports.data ? (
        <Loading />
      ) : reports.error ? (
        <ErrorBanner message={errorMessage(reports.error)} onRetry={reports.reload} />
      ) : (reports.data?.items ?? []).length === 0 ? (
        <EmptyState title="Aucun rapport.">Créez-en un à partir d&apos;une exécution terminée.</EmptyState>
      ) : (
        <Card>
          <Table label="Rapports">
            <thead>
              <tr>
                <th className={thClass}>Titre</th>
                <th className={thClass}>Sections</th>
                <th className={thClass}>Créé le</th>
              </tr>
            </thead>
            <tbody>
              {reports.data?.items.map((r) => (
                <tr key={r.id}>
                  <td className={tdClass}>
                    <Link href={`/reports/${r.id}`} className="font-semibold text-emerald-300 hover:underline">
                      {r.title}
                    </Link>
                  </td>
                  <td className={tdClass}>
                    <span className="flex flex-wrap gap-1">
                      {r.sections.map((s) => (
                        <Badge key={s}>{SECTION_LABEL[s as ReportSection] ?? s}</Badge>
                      ))}
                    </span>
                  </td>
                  <td className={tdClass}>{fmtDate(r.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
    </>
  );
}

export function NewReport({ initialRun }: { initialRun?: string }) {
  const router = useRouter();
  const ai = useAiStatus();
  const runs = useApi(() => api.runs({ status: "succeeded", page_size: 100 }), []);
  return (
    <>
      <PageHeader title="Nouveau rapport" subtitle="Choisissez les sections, les exécutions à comparer et le récit." />
      <Card>
        {runs.loading && !runs.data ? (
          <Loading />
        ) : runs.error ? (
          <ErrorBanner message={errorMessage(runs.error)} onRetry={runs.reload} />
        ) : (runs.data?.items ?? []).length === 0 ? (
          <EmptyState title="Aucune exécution terminée." />
        ) : (
          <ReportBuilderForm
            runs={runs.data?.items ?? []}
            initialRun={initialRun}
            ai={ai}
            onSubmit={async (spec) => {
              const report = await api.createReport(spec);
              router.push(`/reports/${report.id}`);
            }}
          />
        )}
      </Card>
    </>
  );
}

export function ReportView({ reportId }: { reportId: string }) {
  const router = useRouter();
  const report = useApi(() => api.report(reportId), [reportId]);
  const [error, setError] = useState<string | null>(null);

  if (report.loading && !report.data) return <Loading label="Chargement du rapport…" />;
  if (report.error || !report.data) return <ErrorBanner message={errorMessage(report.error)} onRetry={report.reload} />;
  const r = report.data;

  async function remove() {
    if (!window.confirm(`Supprimer le rapport « ${r.title} » ?`)) return;
    try {
      await api.deleteReport(r.id);
      router.push("/reports");
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <>
      <nav aria-label="Fil d'Ariane" className="mb-2 text-xs text-slate-500">
        <Link href="/reports" className="hover:text-slate-300">
          Rapports
        </Link>{" "}
        / <span className="text-slate-300">{r.title}</span>
      </nav>
      <div className="mb-6 flex flex-wrap items-center justify-end gap-2">
        <Link href={`/reports/${r.id}/print`} className={linkButton} target="_blank">
          <Printer className="h-4 w-4" aria-hidden="true" />
          Imprimer / PDF
        </Link>
        <a href={downloads.reportJson(r.id)} className={linkButton} download>
          <Download className="h-4 w-4" aria-hidden="true" />
          Export JSON
        </a>
        <Button variant="danger" onClick={remove} aria-label="Supprimer le rapport">
          <Trash2 className="h-4 w-4" aria-hidden="true" />
        </Button>
      </div>
      {error && (
        <div className="mb-4">
          <ErrorBanner message={error} />
        </div>
      )}
      <ReportDocument
        snapshot={asSnapshot(r.snapshot)}
        hash={r.snapshot_hash}
        tableActions={(section, table) => (
          <a
            href={downloads.reportCsv(r.id, section, table)}
            download
            className="text-xs font-semibold text-cyan-300 hover:underline"
            aria-label={`Exporter en CSV : ${SECTION_LABEL[section]} — ${table}`}
          >
            CSV
          </a>
        )}
      />
    </>
  );
}
