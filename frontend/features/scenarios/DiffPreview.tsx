import { Badge, EmptyState, Table, tdClass, thClass } from "@/components/ui/primitives";
import type { ScenarioPreview } from "@/lib/api/types";

function show(value: unknown): string {
  if (value === undefined || value === null) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  if (typeof value === "number") return value.toLocaleString("fr-FR", { maximumFractionDigits: 4 });
  return String(value);
}

const KIND = { added: { label: "ajouté", tone: "success" }, removed: { label: "retiré", tone: "danger" }, changed: { label: "modifié", tone: "info" } } as const;

/** Effective data vs the base version: field diff and validation of the result. */
export function DiffPreview({ preview }: { preview: ScenarioPreview }) {
  const errors = preview.validation.errors ?? [];
  const warnings = preview.validation.warnings ?? [];
  return (
    <div className="space-y-4">
      {errors.length > 0 && (
        <div role="alert" className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-200">
          <p className="font-semibold">Les données effectives sont invalides :</p>
          <ul className="list-disc pl-5">
            {errors.map((e) => (
              <li key={`${e.code}-${e.path}`}>{e.message}</li>
            ))}
          </ul>
        </div>
      )}
      {warnings.length > 0 && (
        <ul className="list-disc pl-5 text-xs text-amber-200/80">
          {warnings.map((w) => (
            <li key={`${w.code}-${w.path}`}>{w.message}</li>
          ))}
        </ul>
      )}
      {preview.diff.length === 0 ? (
        <EmptyState title="Aucune différence avec la version de base." />
      ) : (
        <Table label="Différences avec la version de base">
          <thead>
            <tr>
              <th className={thClass}>Champ</th>
              <th className={thClass}>Type</th>
              <th className={thClass}>Avant</th>
              <th className={thClass}>Après</th>
            </tr>
          </thead>
          <tbody>
            {preview.diff.map((d) => (
              <tr key={d.path}>
                <td className={`${tdClass} font-mono text-xs`}>{d.path}</td>
                <td className={tdClass}>
                  <Badge tone={KIND[d.kind].tone}>{KIND[d.kind].label}</Badge>
                </td>
                <td className={`${tdClass} max-w-xs truncate font-mono text-xs text-slate-400`} title={show(d.before)}>
                  {show(d.before)}
                </td>
                <td className={`${tdClass} max-w-xs truncate font-mono text-xs text-white`} title={show(d.after)}>
                  {show(d.after)}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </div>
  );
}
