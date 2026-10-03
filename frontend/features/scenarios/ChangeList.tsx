"use client";

import { ArrowDown, ArrowUp, Trash2 } from "lucide-react";
import { Badge, Button, cx, EmptyState } from "@/components/ui/primitives";
import type { AppliedChange, ScenarioChangeOut } from "@/lib/api/types";
import { opLabel } from "./targets";

/** Compact text of a change's params, e.g. `mode=relative_pct, value=-10`. */
export function describeParams(params: Record<string, unknown>): string {
  return Object.entries(params)
    .map(([k, v]) => `${k}=${typeof v === "object" && v !== null ? JSON.stringify(v) : String(v)}`)
    .join(", ");
}

export function ChangeList({
  changes,
  applied = [],
  onToggle,
  onDelete,
  onMove,
  busy = false,
}: {
  changes: ScenarioChangeOut[];
  applied?: AppliedChange[];
  onToggle: (change: ScenarioChangeOut) => void;
  onDelete: (change: ScenarioChangeOut) => void;
  onMove: (change: ScenarioChangeOut, direction: -1 | 1) => void;
  busy?: boolean;
}) {
  if (changes.length === 0) return <EmptyState title="Aucune modification.">Ajoutez-en une avec le formulaire.</EmptyState>;
  const summary = new Map(applied.filter((a) => a.change_id).map((a) => [a.change_id as string, a.summary]));
  const sorted = [...changes].sort((a, b) => a.position - b.position);

  return (
    <ol className="space-y-2" aria-label="Modifications du scénario">
      {sorted.map((c, i) => (
        <li
          key={c.id}
          className={cx("rounded-lg border border-card-border bg-navy-deep p-3", !c.enabled && "opacity-60")}
          data-testid="change-item"
        >
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="flex flex-wrap items-center gap-2 text-sm font-semibold text-white">
                <span className="font-mono text-xs text-slate-500">#{i + 1}</span>
                {opLabel(c.op)}
                {c.target && <Badge>{c.target === "*" ? "tous" : c.target}</Badge>}
                {c.source !== "manual" && <Badge tone="info">{c.source === "recommendation" ? "recommandation" : "IA"}</Badge>}
                {!c.enabled && <Badge>désactivée</Badge>}
              </p>
              <p className="mt-1 text-sm text-slate-300">{summary.get(c.id) ?? describeParams(c.params)}</p>
              {c.note && <p className="mt-1 text-xs text-slate-500">{c.note}</p>}
            </div>
            <div className="flex items-center gap-1">
              <label className="mr-2 flex items-center gap-1 text-xs text-slate-400">
                <input type="checkbox" checked={c.enabled} disabled={busy} onChange={() => onToggle(c)} aria-label={`Activer ${opLabel(c.op)}`} />
                active
              </label>
              <Button variant="ghost" aria-label="Monter" disabled={busy || i === 0} onClick={() => onMove(c, -1)}>
                <ArrowUp className="h-4 w-4" aria-hidden="true" />
              </Button>
              <Button variant="ghost" aria-label="Descendre" disabled={busy || i === sorted.length - 1} onClick={() => onMove(c, 1)}>
                <ArrowDown className="h-4 w-4" aria-hidden="true" />
              </Button>
              <Button variant="ghost" aria-label="Supprimer" disabled={busy} onClick={() => onDelete(c)}>
                <Trash2 className="h-4 w-4 text-rose-300" aria-hidden="true" />
              </Button>
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}

/** New order of change ids after moving `id` one step up (-1) or down (+1). */
export function moveId(ids: string[], id: string, direction: -1 | 1): string[] {
  const i = ids.indexOf(id);
  const j = i + direction;
  if (i < 0 || j < 0 || j >= ids.length) return ids;
  const next = [...ids];
  [next[i], next[j]] = [next[j], next[i]];
  return next;
}
