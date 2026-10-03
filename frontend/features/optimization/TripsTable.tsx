import { cx, numClass, Table, tdClass, thClass } from "@/components/ui/primitives";
import { fmtKg, fmtMoney, fmtNum } from "@/lib/format";
import type { TripRow } from "@/lib/api/types";
import { nameOf, type NameIndex } from "./names";

export function TripsTable({ trips, names = {}, currency }: { trips: TripRow[]; names?: NameIndex; currency?: string }) {
  if (trips.length === 0) return <p className="py-6 text-sm text-slate-400">Aucun trajet planifié.</p>;
  const rows = [...trips].sort((a, b) => a.day - b.day || a.buyer_id.localeCompare(b.buyer_id));
  const total = rows.reduce(
    (acc, t) => ({ trips: acc.trips + t.trips, capacity: acc.capacity + t.capacity_kg, cost: acc.cost + t.cost, hours: acc.hours + t.hours }),
    { trips: 0, capacity: 0, cost: 0, hours: 0 },
  );
  return (
    <Table label="Trajets planifiés">
      <thead>
        <tr>
          <th className={thClass}>Jour</th>
          <th className={thClass}>Acheteur</th>
          <th className={thClass}>Véhicule</th>
          <th className={cx(thClass, "text-right")}>Trajets</th>
          <th className={cx(thClass, "text-right")}>Capacité</th>
          <th className={cx(thClass, "text-right")}>Coût</th>
          <th className={cx(thClass, "text-right")}>Heures</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((t, i) => (
          <tr key={`${t.day}-${t.buyer_id}-${t.vehicle_type_id}-${i}`}>
            <td className={tdClass}>J{t.day}</td>
            <td className={tdClass}>{nameOf(names.buyers, t.buyer_id)}</td>
            <td className={tdClass}>{nameOf(names.vehicles, t.vehicle_type_id)}</td>
            <td className={cx(tdClass, numClass)}>{t.trips}</td>
            <td className={cx(tdClass, numClass)}>{fmtKg(t.capacity_kg)}</td>
            <td className={cx(tdClass, numClass)}>{fmtMoney(t.cost, currency)}</td>
            <td className={cx(tdClass, numClass)}>{fmtNum(t.hours)}</td>
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr>
          <th scope="row" colSpan={3} className={thClass}>
            Total
          </th>
          <td className={cx(tdClass, numClass, "font-bold")}>{total.trips}</td>
          <td className={cx(tdClass, numClass, "font-bold")}>{fmtKg(total.capacity)}</td>
          <td className={cx(tdClass, numClass, "font-bold")}>{fmtMoney(total.cost, currency)}</td>
          <td className={cx(tdClass, numClass, "font-bold")}>{fmtNum(total.hours)}</td>
        </tr>
      </tfoot>
    </Table>
  );
}
