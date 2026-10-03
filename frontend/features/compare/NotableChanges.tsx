import { EmptyState } from "@/components/ui/primitives";
import type { NotableChange } from "@/lib/api/types";

/** Rule-based changes computed by the backend, largest first. */
export function NotableChanges({ changes, labels }: { changes: NotableChange[]; labels: Record<string, string> }) {
  if (changes.length === 0) return <EmptyState title="Aucun changement notable." />;
  const sorted = [...changes].sort((a, b) => b.magnitude - a.magnitude);
  return (
    <ul className="space-y-2" aria-label="Changements notables">
      {sorted.map((c, i) => (
        <li key={`${c.code}-${c.run_id}-${i}`} className="rounded-lg border border-card-border bg-navy-deep px-3 py-2 text-sm text-slate-200">
          <span className="mr-2 text-xs font-semibold text-slate-500">{labels[c.run_id] ?? c.run_id}</span>
          {c.message}
        </li>
      ))}
    </ul>
  );
}
