import { Badge, type Tone } from "@/components/ui/primitives";
import type { ScenarioSummary } from "@/lib/api/types";

const STATUS: Record<ScenarioSummary["status"], { label: string; tone: Tone }> = {
  draft: { label: "Brouillon", tone: "neutral" },
  ready: { label: "Prêt", tone: "success" },
  stale: { label: "Obsolète", tone: "warning" },
  archived: { label: "Archivé", tone: "neutral" },
};

export function ScenarioStatusBadge({ status }: { status: ScenarioSummary["status"] }) {
  return <Badge tone={STATUS[status].tone}>{STATUS[status].label}</Badge>;
}

/** Shown when the dataset has a newer version than the scenario's base (rebase needed). */
export function StaleBadge({ baseVersion, currentVersion }: { baseVersion: number; currentVersion?: number | null }) {
  const title = currentVersion
    ? `Basé sur la v${baseVersion}, les données sont en v${currentVersion} : rebasez pour en tenir compte.`
    : `Basé sur la v${baseVersion}, une version plus récente existe.`;
  return (
    <Badge tone="warning" title={title}>
      Obsolète · v{baseVersion}
      {currentVersion ? ` → v${currentVersion}` : ""}
    </Badge>
  );
}
