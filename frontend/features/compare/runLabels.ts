import { shortId } from "@/lib/format";
import type { ComparisonResult } from "@/lib/api/types";

/** Display name of each run in a comparison: its label, else its short id. */
export function runLabels(result: ComparisonResult): Record<string, string> {
  return Object.fromEntries(result.runs.map((r) => [r.run_id, r.label ?? shortId(r.run_id)]));
}
