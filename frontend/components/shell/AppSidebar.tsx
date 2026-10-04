"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Search, Sprout } from "lucide-react";
import { cx } from "@/components/ui/primitives";
import { openCommandPalette } from "./CommandPalette";
import { NAV } from "./nav";
import { ThemeToggle } from "./ThemeToggle";

export function AppSidebar() {
  const pathname = usePathname();
  return (
    <aside className="border-b border-card-border bg-sidebar-surface lg:fixed lg:inset-y-0 lg:left-0 lg:flex lg:w-60 lg:flex-col lg:border-b-0 lg:border-r">
      <div className="flex items-center gap-2 px-5 py-4 lg:py-6">
        <Sprout className="h-6 w-6 text-emerald-accent" aria-hidden="true" />
        <span className="text-base font-bold text-white">Harvest2Value</span>
        <span className="ml-auto flex items-center gap-1">
          <button
            type="button"
            onClick={openCommandPalette}
            aria-label="Rechercher une page ou une action (Ctrl+K)"
            title="Rechercher (Ctrl+K)"
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-slate-300 hover:bg-white/5"
          >
            <Search className="h-4 w-4" aria-hidden="true" />
          </button>
          <ThemeToggle />
        </span>
      </div>
      <nav aria-label="Navigation principale" className="overflow-x-auto px-3 pb-3 lg:flex-1 lg:overflow-y-auto">
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
      <p className="hidden px-5 pb-4 text-xs text-slate-500 lg:block">
        <kbd className="rounded border border-card-border px-1 font-mono">Ctrl</kbd> + <kbd className="rounded border border-card-border px-1 font-mono">K</kbd>{" "}
        pour tout trouver
      </p>
    </aside>
  );
}
