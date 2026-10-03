"use client";

import { Layer, Rectangle, ResponsiveContainer, Sankey, Tooltip } from "recharts";
import type { NodeProps } from "recharts/types/chart/Sankey";
import { CHART, tooltipStyle } from "./theme";

export type FlowNodeKind = "harvest" | "storage" | "direct" | "buyer" | "loss" | "stock";

export interface FlowNode {
  id: string;
  label: string;
  kind: FlowNodeKind;
}

export interface FlowLink {
  source: string;
  target: string;
  value: number;
}

export interface FlowGraph {
  nodes: FlowNode[];
  links: FlowLink[];
}

export const FLOW_COLORS: Record<FlowNodeKind, string> = {
  harvest: "#10B981",
  storage: "#F59E0B",
  direct: "#06B6D4",
  buyer: "#38BDF8",
  loss: "#F43F5E",
  stock: "#A78BFA",
};

interface RechartsNode {
  name: string;
  kind: FlowNodeKind;
}

interface RechartsLink {
  source: number;
  target: number;
  value: number;
}

/** Index-based links as recharts expects; links below `minValue` and orphan nodes are dropped. */
export function toRechartsSankey(graph: FlowGraph, minValue = 0.5): { nodes: RechartsNode[]; links: RechartsLink[] } {
  const links = graph.links.filter((l) => l.value >= minValue);
  const used = new Set(links.flatMap((l) => [l.source, l.target]));
  const nodes = graph.nodes.filter((n) => used.has(n.id));
  const index = new Map(nodes.map((n, i) => [n.id, i]));
  return {
    nodes: nodes.map((n) => ({ name: n.label, kind: n.kind })),
    links: links.map((l) => ({ source: index.get(l.source) as number, target: index.get(l.target) as number, value: l.value })),
  };
}

const LABEL_MAX = 26;

function makeNodeRenderer(nodes: RechartsNode[]) {
  return function FlowNodeShape({ x, y, width: w, height, index, payload }: NodeProps) {
    const kind = nodes[index]?.kind ?? "buyer";
    return (
      <Layer key={`node-${index}`}>
        <Rectangle x={x} y={y} width={w} height={height} fill={FLOW_COLORS[kind]} fillOpacity={0.95} radius={2} />
        <text
          x={x + w + 6}
          y={y + height / 2}
          textAnchor="start"
          dominantBaseline="middle"
          fontSize={12}
          fill="#E2E8F0"
        >
          <title>{payload.name}</title>
          {payload.name.length > LABEL_MAX ? `${payload.name.slice(0, LABEL_MAX - 1)}…` : payload.name}
        </text>
      </Layer>
    );
  };
}

export function SankeyChart({
  graph,
  height = 360,
  formatValue = (v: number) => `${Math.round(v).toLocaleString("fr-FR")} kg`,
}: {
  graph: FlowGraph;
  height?: number;
  formatValue?: (value: number) => string;
}) {
  const data = toRechartsSankey(graph);
  if (data.links.length === 0) {
    return <p className="py-10 text-center text-sm text-slate-500">Aucun flux à afficher.</p>;
  }
  const renderNode = makeNodeRenderer(data.nodes);
  return (
    <div role="img" aria-label="Flux de la récolte vers les entrepôts, les acheteurs et les pertes" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <Sankey
          data={data}
          node={renderNode}
          nodePadding={18}
          nodeWidth={12}
          margin={{ top: 10, right: 190, bottom: 10, left: 10 }}
          link={{ stroke: CHART.axis, strokeOpacity: 0.35 }}
        >
          <Tooltip {...tooltipStyle} formatter={(value) => (typeof value === "number" ? formatValue(value) : String(value))} />
        </Sankey>
      </ResponsiveContainer>
    </div>
  );
}
