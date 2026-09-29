"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  Bot,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  LayoutDashboard,
  LogOut,
  Settings,
  Sprout,
  Users,
  Warehouse,
  type LucideIcon,
} from "lucide-react";

interface NavItem {
  icon: LucideIcon;
  label: string;
  href: string;
}

const NAV_ITEMS: NavItem[] = [
  { icon: LayoutDashboard, label: "Dashboard", href: "/dashboard" },
  { icon: Users, label: "Farmers", href: "/farmers" },
  { icon: Warehouse, label: "Storage Facilities", href: "/storage" },
  { icon: BarChart3, label: "Analytics", href: "/analytics" },
  { icon: Bot, label: "AI Assistant", href: "/ai-assistant" },
  { icon: Settings, label: "Settings", href: "/settings" },
  { icon: CircleHelp, label: "Help & Support", href: "/support" },
];

const ITEM_BASE =
  "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium outline-none transition-colors " +
  "focus-visible:ring-2 focus-visible:ring-accent";

interface SidebarProps {
  /** Log Out handler: clears auth state and navigates to the landing page. */
  onLogout: () => void;
}

/**
 * Collapsible dashboard sidebar. It sits in normal flow (sticky, full height)
 * so the content next to it reflows when it collapses to icon-only mode.
 */
export default function Sidebar({ onLogout }: SidebarProps) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={`sticky top-0 hidden h-screen shrink-0 flex-col justify-between border-r border-card-border bg-sidebar-surface py-5 transition-[width] duration-200 lg:flex ${
        collapsed ? "w-[72px] px-3" : "w-64 px-4"
      }`}
    >
      <div>
        <div className={`mb-6 flex items-center ${collapsed ? "flex-col gap-3" : "justify-between px-1"}`}>
          <Link
            href="/dashboard"
            aria-label="Harvest2Value dashboard"
            className="flex items-center gap-2 rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            <Sprout className="h-7 w-7 shrink-0 text-accent-text" aria-hidden="true" />
            {!collapsed && <span className="text-lg font-bold text-text-primary">Harvest2Value</span>}
          </Link>
          <button
            type="button"
            onClick={() => setCollapsed((c) => !c)}
            aria-expanded={!collapsed}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-card-border text-text-secondary outline-none hover:border-accent/50 hover:text-text-primary focus-visible:ring-2 focus-visible:ring-accent"
          >
            {collapsed ? (
              <ChevronRight className="h-4 w-4" aria-hidden="true" />
            ) : (
              <ChevronLeft className="h-4 w-4" aria-hidden="true" />
            )}
          </button>
        </div>

        <nav aria-label="Main navigation">
          <ul className="space-y-1">
            {NAV_ITEMS.map(({ icon: Icon, label, href }) => {
              const active = pathname === href || pathname.startsWith(`${href}/`);
              return (
                <li key={href}>
                  <Link
                    href={href}
                    aria-current={active ? "page" : undefined}
                    aria-label={collapsed ? label : undefined}
                    title={collapsed ? label : undefined}
                    className={`${ITEM_BASE} ${collapsed ? "justify-center" : ""} ${
                      active
                        ? "bg-accent/10 font-semibold text-accent-text"
                        : "text-text-secondary hover:bg-accent/5 hover:text-text-primary"
                    }`}
                  >
                    <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
                    {!collapsed && <span className="truncate">{label}</span>}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>

      <button
        type="button"
        onClick={onLogout}
        aria-label={collapsed ? "Log Out" : undefined}
        title={collapsed ? "Log Out" : undefined}
        className={`${ITEM_BASE} w-full text-text-secondary hover:bg-danger/10 hover:text-danger ${
          collapsed ? "justify-center" : ""
        }`}
      >
        <LogOut className="h-5 w-5 shrink-0" aria-hidden="true" />
        {!collapsed && <span>Log Out</span>}
      </button>
    </aside>
  );
}
