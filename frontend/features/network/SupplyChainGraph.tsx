"use client";

import "@xyflow/react/dist/style.css";
import { Background, Controls, Handle, Position, ReactFlow, type NodeProps } from "@xyflow/react";
import { useMemo } from "react";
import type { NetworkGraph } from "@/lib/api/types";
import { layoutNetwork, type SupplyNode } from "./layout";

const KIND_STYLE: Record<SupplyNode["data"]["kind"], { label: string; color: string }> = {
  producer: { label: "Producteur", color: "#10B981" },
  lot: { label: "Lot", color: "#84CC16" },
  storage: { label: "Entrepôt", color: "#F59E0B" },
  direct: { label: "Vente directe", color: "#06B6D4" },
  vehicle: { label: "Véhicules", color: "#A78BFA" },
  buyer: { label: "Acheteur", color: "#38BDF8" },
};

const METRIC_LABEL: Record<string, string> = {
  harvest_kg: "récolte",
  quantity_kg: "quantité",
  day: "jour",
  capacity_kg: "capacité",
  peak_pct: "pic %",
  stock_end_kg: "stock",
  count: "nombre",
  sold_kg: "vendu",
  revenue: "revenu",
  fulfillment_pct: "servi %",
};

function formatMetric(v: string | number | null | undefined): string {
  if (v == null) return "—";
  return typeof v === "number" ? v.toLocaleString("fr-FR", { maximumFractionDigits: 1 }) : v;
}

function SupplyNodeView({ data }: NodeProps<SupplyNode>) {
  const style = KIND_STYLE[data.kind];
  const metrics = Object.entries(data.metrics).filter(([k]) => k in METRIC_LABEL).slice(0, 3);
  return (
    <div className="w-48 rounded-lg border bg-card-surface px-3 py-2 text-left shadow" style={{ borderColor: style.color }}>
      <Handle type="target" position={Position.Left} className="!bg-slate-500" />
      <p className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: style.color }}>
        {style.label}
      </p>
      <p className="truncate text-xs font-semibold text-white" title={data.label}>
        {data.label}
      </p>
      {metrics.length > 0 && (
        <p className="mt-1 truncate text-[10px] text-slate-400">
          {metrics.map(([k, v]) => `${METRIC_LABEL[k]} ${formatMetric(v)}`).join(" · ")}
        </p>
      )}
      <Handle type="source" position={Position.Right} className="!bg-slate-500" />
    </div>
  );
}

const nodeTypes = { supply: SupplyNodeView };

export function SupplyChainGraph({ graph, height = 560 }: { graph: NetworkGraph; height?: number }) {
  const { nodes, edges } = useMemo(() => layoutNetwork(graph), [graph]);
  return (
    <div
      style={{ height }}
      className="overflow-hidden rounded-xl border border-card-border bg-navy-deep"
      role="img"
      aria-label={`Réseau logistique ${graph.day == null ? "sur toute la période" : `du jour ${graph.day}`} : ${nodes.length} nœuds, ${edges.length} flux`}
      data-testid="supply-chain-graph"
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        nodesDraggable={false}
        nodesConnectable={false}
        proOptions={{ hideAttribution: true }}
        colorMode="dark"
        minZoom={0.2}
      >
        <Background color="#1E293B" gap={20} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
