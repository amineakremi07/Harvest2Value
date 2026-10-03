import type { Edge, Node } from "@xyflow/react";
import type { NetworkEdge, NetworkGraph, NetworkNode } from "@/lib/api/types";

export type NetworkNodeKind = NetworkNode["kind"];

export interface SupplyNodeData extends Record<string, unknown> {
  label: string;
  kind: NetworkNodeKind;
  metrics: NetworkNode["metrics"];
}

export type SupplyNode = Node<SupplyNodeData, "supply">;
export type SupplyEdge = Edge<{ kind: NetworkEdge["kind"]; kg: number; value: number | null; trips: number | null }>;

/** Left-to-right columns: producer -> lots -> storage / direct sale -> vehicles -> buyers. */
export const COLUMN: Record<NetworkNodeKind, number> = { producer: 0, lot: 1, storage: 2, direct: 2, vehicle: 3, buyer: 4 };
export const COLUMN_GAP = 260;
export const ROW_GAP = 100;

export const EDGE_COLOR: Record<NetworkEdge["kind"], string> = {
  harvest: "#10B981",
  placement: "#F59E0B",
  sale: "#38BDF8",
  transport: "#A78BFA",
};

/** Deterministic column layout; nodes without any edge for the selected day are dropped. */
export function layoutNetwork(graph: NetworkGraph, { hideIdle = true }: { hideIdle?: boolean } = {}): { nodes: SupplyNode[]; edges: SupplyEdge[] } {
  const used = new Set(graph.edges.flatMap((e) => [e.source, e.target]));
  const kept = graph.nodes.filter((n) => !hideIdle || n.kind === "producer" || n.kind === "buyer" || used.has(n.id));

  const columns = new Map<number, NetworkNode[]>();
  for (const n of kept) {
    const col = COLUMN[n.kind];
    columns.set(col, [...(columns.get(col) ?? []), n]);
  }
  const tallest = Math.max(1, ...[...columns.values()].map((c) => c.length));

  const nodes: SupplyNode[] = [];
  for (const [col, list] of columns) {
    const offset = ((tallest - list.length) * ROW_GAP) / 2;
    list.forEach((n, row) => {
      nodes.push({
        id: n.id,
        type: "supply",
        position: { x: col * COLUMN_GAP, y: offset + row * ROW_GAP },
        data: { label: n.label, kind: n.kind, metrics: n.metrics },
        draggable: false,
      });
    });
  }

  const ids = new Set(nodes.map((n) => n.id));
  const maxKg = Math.max(1, ...graph.edges.map((e) => e.kg));
  const edges: SupplyEdge[] = graph.edges
    .filter((e) => ids.has(e.source) && ids.has(e.target))
    .map((e, i) => ({
      id: `${e.source}->${e.target}-${i}`,
      source: e.source,
      target: e.target,
      label: e.kind === "transport" ? `${e.trips ?? 0} trajet(s)` : `${Math.round(e.kg).toLocaleString("fr-FR")} kg`,
      animated: e.kind === "sale",
      style: { stroke: EDGE_COLOR[e.kind], strokeWidth: 1 + 5 * (e.kg / maxKg), strokeOpacity: 0.8 },
      labelStyle: { fill: "#CBD5E1", fontSize: 10 },
      labelBgStyle: { fill: "#0B101D" },
      data: { kind: e.kind, kg: e.kg, value: e.value ?? null, trips: e.trips ?? null },
    }));
  return { nodes, edges };
}
