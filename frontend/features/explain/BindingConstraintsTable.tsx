"use client";

import { useMemo, useState } from "react";
import { Button, cx, inputClass, numClass, Table, tdClass, thClass } from "@/components/ui/primitives";
import { InfoTip } from "@/components/ui/InfoTip";
import { fmtNum } from "@/lib/format";
import type { ConstraintInfo } from "@/lib/api/types";
import { DUAL_TOOLTIP, familyLabel } from "./labels";

const PAGE = 15;

/** Constraints that bind in the optimal plan, filterable by family. */
export function BindingConstraintsTable({ constraints }: { constraints: ConstraintInfo[] }) {
  const [family, setFamily] = useState("");
  const [limit, setLimit] = useState(PAGE);
  const families = useMemo(() => [...new Set(constraints.map((c) => c.family))].sort(), [constraints]);
  const rows = constraints.filter((c) => !family || c.family === family);

  if (constraints.length === 0) return <p className="text-sm text-slate-400">Aucune contrainte saturée.</p>;
  return (
    <div className="space-y-3">
      <select
        aria-label="Filtrer par famille"
        className={cx(inputClass, "w-auto")}
        value={family}
        onChange={(e) => {
          setFamily(e.target.value);
          setLimit(PAGE);
        }}
      >
        <option value="">Toutes les familles ({constraints.length})</option>
        {families.map((f) => (
          <option key={f} value={f}>
            {familyLabel(f)} ({constraints.filter((c) => c.family === f).length})
          </option>
        ))}
      </select>
      <Table label="Contraintes saturées">
        <thead>
          <tr>
            <th className={thClass}>Contrainte</th>
            <th className={thClass}>Famille</th>
            <th className={thClass}>Jour</th>
            <th className={cx(thClass, "text-right")}>Valeur / limite</th>
            <th className={cx(thClass, "text-right")}>
              <span className="inline-flex items-center gap-1">
                Indicateur local <InfoTip label="Limites de l'indicateur local">{DUAL_TOOLTIP}</InfoTip>
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, limit).map((c) => (
            <tr key={c.key}>
              <td className={tdClass}>{c.label}</td>
              <td className={tdClass}>{familyLabel(c.family)}</td>
              <td className={tdClass}>{c.day == null ? "—" : `J${c.day}`}</td>
              <td className={cx(tdClass, numClass)}>
                {fmtNum(c.lhs)} {c.sense} {fmtNum(c.rhs)}
              </td>
              <td className={cx(tdClass, numClass, c.dual_reliable ? "text-slate-200" : "text-slate-600")}>
                {c.dual == null ? "—" : fmtNum(c.dual)}
                {c.dual != null && !c.dual_reliable && <span className="ml-1 text-[10px]">(peu fiable)</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
      {rows.length > limit && (
        <Button variant="ghost" onClick={() => setLimit((l) => l + PAGE * 2)}>
          Afficher plus ({rows.length - limit} restantes)
        </Button>
      )}
    </div>
  );
}
