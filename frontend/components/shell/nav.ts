import {
  BarChart3,
  Bot,
  Database,
  FileText,
  GitBranch,
  History,
  LayoutDashboard,
  LineChart,
  Settings,
  SlidersHorizontal,
} from "lucide-react";

/** Main navigation: the sidebar and the command palette share it. */
export const NAV = [
  { href: "/dashboard", label: "Tableau de bord", icon: LayoutDashboard },
  { href: "/datasets", label: "Données", icon: Database },
  { href: "/optimize", label: "Optimiser", icon: SlidersHorizontal },
  { href: "/runs", label: "Exécutions", icon: History },
  { href: "/scenarios", label: "Scénarios", icon: GitBranch },
  { href: "/compare", label: "Comparer", icon: BarChart3 },
  { href: "/analytics", label: "Analyses", icon: LineChart },
  { href: "/reports", label: "Rapports", icon: FileText },
  { href: "/copilot", label: "Copilot", icon: Bot },
  { href: "/settings", label: "Réglages", icon: Settings },
] as const;
