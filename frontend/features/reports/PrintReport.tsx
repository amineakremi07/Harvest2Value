"use client";

import { Printer } from "lucide-react";
import { errorMessage } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import { useApi } from "@/lib/hooks/useApi";
import { asSnapshot, ReportDocument } from "./ReportDocument";

/** Paper version of a frozen report: print it, or "Save as PDF" from the browser dialog. */
export function PrintReport({ reportId }: { reportId: string }) {
  const report = useApi(() => api.report(reportId), [reportId]);
  if (report.error) return <p className="p-8 text-rose-700">{errorMessage(report.error)}</p>;
  if (!report.data) return <p className="p-8 text-slate-500">Chargement du rapport…</p>;
  return (
    <div className="mx-auto max-w-4xl p-8 print:max-w-none print:p-0">
      <div className="no-print mb-6 flex justify-end">
        <button
          type="button"
          onClick={() => window.print()}
          className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-700"
        >
          <Printer className="h-4 w-4" aria-hidden="true" />
          Imprimer / Enregistrer en PDF
        </button>
      </div>
      <ReportDocument snapshot={asSnapshot(report.data.snapshot)} hash={report.data.snapshot_hash} />
    </div>
  );
}
