import Link from "next/link";
import { Card, EmptyState } from "@/components/ui/primitives";
import type { InsightView } from "@/lib/api/types";
import { InsightCard } from "@/features/insights/InsightCard";

/** Risks of the run, most severe first (opportunities go to TopRecommendations). */
export function AlertsPanel({ insights, runId }: { insights: InsightView[]; runId: string }) {
  const risks = insights.filter((i) => i.category !== "opportunity");
  return (
    <Card
      title="Alertes"
      actions={
        <Link href={`/runs/${runId}/insights`} className="text-xs font-semibold text-cyan-300 hover:underline">
          Tout voir
        </Link>
      }
    >
      {risks.length === 0 ? (
        <EmptyState title="Aucune alerte sur le dernier plan." />
      ) : (
        <div className="space-y-2">
          {risks.map((i) => (
            <InsightCard key={i.id} insight={i} compact />
          ))}
        </div>
      )}
    </Card>
  );
}
