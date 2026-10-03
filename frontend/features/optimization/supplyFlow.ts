import type { FlowGraph, FlowLink, FlowNode } from "@/components/charts/SankeyChart";
import type { OptimizationResult } from "@/lib/api/types";
import type { NameIndex } from "./names";

const HARVEST = "harvest";
const DIRECT = "direct";
const LOSS = "loss";
const STOCK = "stock";

function add(map: Map<string, number>, key: string, kg: number) {
  map.set(key, (map.get(key) ?? 0) + kg);
}

/**
 * Harvest -> storage facility (or direct sale) -> buyers, with losses and the ending stock as
 * sinks. Every value is a solver quantity from the result (kg); nothing is estimated.
 */
export function supplyFlow(result: OptimizationResult, names: NameIndex = {}): FlowGraph {
  const sold = new Map<string, number>(); // "facility|buyer" -> kg
  const lost = new Map<string, number>(); // facility (or DIRECT) -> kg
  const facilities = new Set<string>();

  for (const row of result.allocations) {
    const via = row.facility_id ?? DIRECT;
    if (row.facility_id) facilities.add(row.facility_id);
    add(sold, `${via}|${row.buyer_id}`, row.kg);
  }
  for (const row of result.waste) {
    const via = row.facility_id ?? DIRECT;
    if (row.facility_id) facilities.add(row.facility_id);
    add(lost, via, row.kg);
  }

  // Ending stock: inventory on the last day of the horizon, per facility. Inventory rows are
  // sparse (only days with stock), so the last row is not necessarily the horizon's end.
  const lastDay = result.horizon_days - 1;
  const stock = new Map<string, number>();
  for (const row of result.inventory) {
    facilities.add(row.facility_id);
    if (row.day === lastDay) add(stock, row.facility_id, row.kg_end);
  }

  const buyerName = new Map(result.buyers.map((b) => [b.buyer_id, b.buyer_name]));
  const nodes: FlowNode[] = [{ id: HARVEST, label: "Récolte", kind: "harvest" }];
  const links: FlowLink[] = [];

  const inflow = new Map<string, number>();
  for (const [key, kg] of sold) add(inflow, key.split("|")[0], kg);
  for (const [via, kg] of lost) if (via !== DIRECT) add(inflow, via, kg);
  for (const [via, kg] of stock) add(inflow, via, kg);

  if ((inflow.get(DIRECT) ?? 0) > 0) nodes.push({ id: DIRECT, label: "Vente directe", kind: "direct" });
  for (const f of [...facilities].sort()) {
    nodes.push({ id: `f:${f}`, label: names.facilities?.[f] ?? f, kind: "storage" });
  }
  for (const [via, kg] of inflow) links.push({ source: HARVEST, target: via === DIRECT ? DIRECT : `f:${via}`, value: kg });

  const buyers = new Set<string>();
  for (const [key, kg] of sold) {
    const [via, buyer] = key.split("|");
    buyers.add(buyer);
    links.push({ source: via === DIRECT ? DIRECT : `f:${via}`, target: `b:${buyer}`, value: kg });
  }
  for (const b of [...buyers].sort()) nodes.push({ id: `b:${b}`, label: buyerName.get(b) ?? b, kind: "buyer" });

  if (lost.size > 0) nodes.push({ id: LOSS, label: "Pertes", kind: "loss" });
  for (const [via, kg] of lost) {
    // Unsold on the harvest day without storage: lost straight from the harvest.
    links.push({ source: via === DIRECT ? HARVEST : `f:${via}`, target: LOSS, value: kg });
  }
  if (stock.size > 0) nodes.push({ id: STOCK, label: "Stock final", kind: "stock" });
  for (const [f, kg] of stock) links.push({ source: `f:${f}`, target: STOCK, value: kg });

  return { nodes, links };
}
