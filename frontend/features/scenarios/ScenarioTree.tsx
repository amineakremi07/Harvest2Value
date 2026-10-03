import Link from "next/link";
import { GitBranch } from "lucide-react";
import { cx } from "@/components/ui/primitives";
import type { ScenarioSummary } from "@/lib/api/types";
import { ScenarioStatusBadge } from "./StaleBadge";

export interface TreeNode {
  scenario: ScenarioSummary;
  children: TreeNode[];
}

/** Parent -> children forest; scenarios whose parent is not in the list become roots. */
export function buildForest(scenarios: ScenarioSummary[]): TreeNode[] {
  const nodes = new Map(scenarios.map((s) => [s.id, { scenario: s, children: [] as TreeNode[] }]));
  const roots: TreeNode[] = [];
  for (const node of nodes.values()) {
    const parent = node.scenario.parent_id ? nodes.get(node.scenario.parent_id) : undefined;
    (parent ? parent.children : roots).push(node);
  }
  const sort = (list: TreeNode[]) => {
    list.sort((a, b) => a.scenario.created_at.localeCompare(b.scenario.created_at));
    list.forEach((n) => sort(n.children));
  };
  sort(roots);
  return roots;
}

function Branch({ node, activeId }: { node: TreeNode; activeId?: string }) {
  const active = node.scenario.id === activeId;
  return (
    <li>
      <div className="flex items-center gap-2 py-1">
        <GitBranch className="h-3.5 w-3.5 shrink-0 text-slate-500" aria-hidden="true" />
        <Link
          href={`/scenarios/${node.scenario.id}`}
          aria-current={active ? "page" : undefined}
          className={cx("truncate text-sm hover:underline", active ? "font-semibold text-white" : "text-cyan-300")}
        >
          {node.scenario.name}
        </Link>
        <ScenarioStatusBadge status={node.scenario.status} />
      </div>
      {node.children.length > 0 && (
        <ul className="ml-2 border-l border-card-border pl-4">
          {node.children.map((child) => (
            <Branch key={child.scenario.id} node={child} activeId={activeId} />
          ))}
        </ul>
      )}
    </li>
  );
}

export function ScenarioTree({ scenarios, activeId }: { scenarios: ScenarioSummary[]; activeId?: string }) {
  const forest = buildForest(scenarios);
  if (forest.length === 0) return <p className="text-sm text-slate-400">Aucun scénario.</p>;
  return (
    <ul aria-label="Arbre des scénarios">
      {forest.map((node) => (
        <Branch key={node.scenario.id} node={node} activeId={activeId} />
      ))}
    </ul>
  );
}
