import Link from "next/link";
import { Badge, Card, EmptyState } from "@/components/ui/primitives";
import { fmtDate, fmtMoney, shortId } from "@/lib/format";
import type { RunSummary } from "@/lib/api/types";
import { RUN_STATUS_LABEL, RUN_STATUS_TONE } from "@/features/optimization/runStatus";

export function RecentRuns({ runs }: { runs: RunSummary[] }) {
  return (
    <Card
      title="Exécutions récentes"
      actions={
        <Link href="/runs" className="text-xs font-semibold text-cyan-300 hover:underline">
          Historique
        </Link>
      }
    >
      {runs.length === 0 ? (
        <EmptyState title="Aucune exécution." />
      ) : (
        <ul className="divide-y divide-card-border">
          {runs.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
              <Link href={`/runs/${r.id}/summary`} className="min-w-0 truncate font-medium text-cyan-300 hover:underline">
                {r.label ?? shortId(r.id)}
              </Link>
              <span className="flex items-center gap-3">
                <span className="font-mono text-slate-300">{fmtMoney(r.headline?.realized_profit)}</span>
                <Badge tone={RUN_STATUS_TONE[r.status]}>{RUN_STATUS_LABEL[r.status]}</Badge>
                <span className="text-xs text-slate-500">{fmtDate(r.created_at)}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
