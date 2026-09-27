import { Sprout, LayoutDashboard, FileText, BarChart3, UserCircle2 } from "lucide-react";

interface NavItem {
  icon: typeof LayoutDashboard;
  label: string;
  active?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { icon: LayoutDashboard, label: "Dashboard", active: true },
];

export default function Sidebar() {
  return (
    <aside className="hidden w-64 shrink-0 flex-col justify-between border-r border-[#1E293B] bg-[#0B101D] p-6 lg:fixed lg:inset-y-0 lg:left-0 lg:flex">
      <div>
        <div className="mb-10 flex items-center gap-2">
          <Sprout className="h-7 w-7 text-[#10B981]" aria-hidden="true" />
          <span className="text-lg font-bold text-white">Harvest2Value</span>
        </div>

        <nav aria-label="Main navigation">
          <ul className="space-y-1">
            {NAV_ITEMS.map(({ icon: Icon, label, active }) => (
              <li key={label}>
                {active ? (
                  <span
                    aria-current="page"
                    className="flex items-center gap-3 rounded-lg border-l-4 border-[#10B981] bg-[#131B2E] px-3 py-2.5 text-sm font-semibold text-white"
                  >
                    <Icon className="h-5 w-5 text-[#10B981]" aria-hidden="true" />
                    <span>{label}</span>
                  </span>
                ) : (
                  <span
                    aria-disabled="true"
                    title="Not available in this sprint"
                    className="flex cursor-not-allowed items-center gap-3 rounded-lg border-l-4 border-transparent px-3 py-2.5 text-sm font-medium text-slate-500"
                  >
                    <Icon className="h-5 w-5" aria-hidden="true" />
                    <span>{label}</span>
                  </span>
                )}
              </li>
            ))}
          </ul>
        </nav>
      </div>

      <div className="flex items-center gap-3 rounded-xl border border-[#1E293B] bg-[#131B2E] p-3">
        <UserCircle2 className="h-9 w-9 text-[#10B981]" aria-hidden="true" />
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-white">My Farm</p>
          <p className="truncate text-xs text-slate-400">Producer account</p>
        </div>
      </div>
    </aside>
  );
}
