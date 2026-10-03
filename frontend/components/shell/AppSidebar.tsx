"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, Bot, FileText, GitBranch, History, LayoutDashboard, LineChart, Settings, SlidersHorizontal, Sprout } from "lucide-react";
import { cx } from "@/components/ui/primitives";

const NAV = [
  { href: "/dashboard", label: "Tableau de bord", icon: LayoutDashboard },
  { href: "/optimize", label: "Optimiser", icon: SlidersHorizontal },
  { href: "/runs", label: "Exécutions", icon: History },
  { href: "/scenarios", label: "Scénarios", icon: GitBranch },
  { href: "/compare", label: "Comparer", icon: BarChart3 },
  { href: "/analytics", label: "Analyses", icon: LineChart },
  { href: "/reports", label: "Rapports", icon: FileText },
  { href: "/copilot", label: "Copilot", icon: Bot },
  { href: "/settings", label: "Réglages", icon: Settings },
] as const;

export function AppSidebar() {
  const pathname = usePathname();
  return (
    <aside className="border-b border-card-border bg-sidebar-surface lg:fixed lg:inset-y-0 lg:left-0 lg:w-60 lg:border-b-0 lg:border-r">
      <div className="flex items-center gap-2 px-5 py-4 lg:py-6">
        <Sprout className="h-6 w-6 text-emerald-accent" aria-hidden="true" />
        <span className="text-base font-bold text-white">Harvest2Value</span>
        <span className="rounded bg-emerald-500/15 px-1.5 text-[10px] font-bold text-emerald-300">V2</span>
      </div>
      <nav aria-label="Navigation principale" className="overflow-x-auto px-3 pb-3">
        <ul className="flex gap-1 lg:flex-col">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || pathname.startsWith(`${href}/`);
            return (
              <li key={href}>
                <Link
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={cx(
                    "flex items-center gap-3 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium",
                    active ? "bg-card-surface text-white" : "text-slate-400 hover:bg-white/5 hover:text-slate-200",
                  )}
                >
                  <Icon className={cx("h-4 w-4", active && "text-emerald-accent")} aria-hidden="true" />
                  {label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
}
