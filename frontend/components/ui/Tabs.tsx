"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cx } from "./primitives";

export interface TabLink {
  href: string;
  label: string;
  muted?: boolean;
}

/** Route-based tabs: the active tab is the one whose href matches the current path. */
export function LinkTabs({ tabs, label }: { tabs: TabLink[]; label: string }) {
  const pathname = usePathname();
  return (
    <nav aria-label={label} className="mb-6 overflow-x-auto border-b border-card-border">
      <ul className="flex min-w-max gap-1">
        {tabs.map((tab) => {
          const active = pathname === tab.href;
          return (
            <li key={tab.href}>
              <Link
                href={tab.href}
                aria-current={active ? "page" : undefined}
                className={cx(
                  "inline-block border-b-2 px-3 py-2 text-sm font-semibold",
                  active ? "border-emerald-accent text-white" : "border-transparent text-slate-400 hover:text-slate-200",
                  tab.muted && !active && "text-slate-600",
                )}
              >
                {tab.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
