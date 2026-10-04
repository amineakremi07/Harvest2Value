"use client";

import { Command } from "cmdk";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Database, FileText, GitBranch, History, Moon, Plus, Sun } from "lucide-react";
import { api } from "@/lib/api/endpoints";
import type { DatasetSummary, ReportSummary, RunSummary, ScenarioSummary } from "@/lib/api/types";
import { fmtDate, shortId } from "@/lib/format";
import { useTheme } from "@/lib/theme/useTheme";
import { NAV } from "./nav";

const OPEN_EVENT = "h2v-command-palette";

export function openCommandPalette(): void {
  window.dispatchEvent(new Event(OPEN_EVENT));
}

type Entities = { runs: RunSummary[]; datasets: DatasetSummary[]; scenarios: ScenarioSummary[]; reports: ReportSummary[] };
const EMPTY: Entities = { runs: [], datasets: [], scenarios: [], reports: [] };

const itemClass =
  "flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-sm text-slate-200 data-[selected=true]:bg-white/10 data-[selected=true]:text-white";
const groupClass = "[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-slate-500";

/** Ctrl+K / ⌘K: jump to any page, recent run, dataset, scenario or report, or run a quick action. */
export function CommandPalette() {
  const router = useRouter();
  const { theme, setChoice } = useTheme();
  const [open, setOpen] = useState(false);
  const [entities, setEntities] = useState<Entities>(EMPTY);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    const onOpen = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener(OPEN_EVENT, onOpen);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener(OPEN_EVENT, onOpen);
    };
  }, []);

  useEffect(() => {
    if (!open) return;
    let live = true;
    // Best effort: the palette still navigates if the API is down.
    Promise.allSettled([api.runs({ page_size: 15 }), api.datasets({ page_size: 15 }), api.scenarios({ page_size: 15 }), api.reports()]).then(
      ([runs, datasets, scenarios, reports]) => {
        if (!live) return;
        setEntities({
          runs: runs.status === "fulfilled" ? runs.value.items : [],
          datasets: datasets.status === "fulfilled" ? datasets.value.items : [],
          scenarios: scenarios.status === "fulfilled" ? scenarios.value.items : [],
          reports: reports.status === "fulfilled" ? reports.value.items.slice(0, 10) : [],
        });
      },
    );
    return () => {
      live = false;
    };
  }, [open]);

  const go = (href: string) => {
    setOpen(false);
    router.push(href);
  };

  return (
    <Command.Dialog
      open={open}
      onOpenChange={setOpen}
      label="Palette de commandes"
      className="app-shell fixed left-1/2 top-[12vh] z-[60] w-[calc(100%-2rem)] max-w-xl -translate-x-1/2 overflow-hidden rounded-xl border border-card-border bg-sidebar-surface shadow-2xl"
      overlayClassName="fixed inset-0 z-[55] bg-black/50"
    >
      <Command.Input
        placeholder="Aller à une page, une exécution, un scénario…"
        aria-label="Rechercher"
        className="w-full border-b border-card-border bg-transparent px-4 py-3 text-sm text-white placeholder:text-slate-500 focus:outline-none"
      />
      <Command.List className="max-h-[60vh] overflow-y-auto p-2">
        <Command.Empty className="px-3 py-6 text-center text-sm text-slate-400">Aucun résultat.</Command.Empty>
        <Command.Group heading="Pages" className={groupClass}>
          {NAV.map(({ href, label, icon: Icon }) => (
            <Command.Item key={href} value={`page ${label}`} onSelect={() => go(href)} className={itemClass}>
              <Icon className="h-4 w-4 text-slate-400" aria-hidden="true" />
              {label}
            </Command.Item>
          ))}
        </Command.Group>
        <Command.Group heading="Actions" className={groupClass}>
          <Command.Item value="action importer un fichier de données" onSelect={() => go("/datasets?import=1")} className={itemClass}>
            <Plus className="h-4 w-4 text-slate-400" aria-hidden="true" />
            Importer des données
          </Command.Item>
          <Command.Item value="action nouveau rapport" onSelect={() => go("/reports/new")} className={itemClass}>
            <Plus className="h-4 w-4 text-slate-400" aria-hidden="true" />
            Nouveau rapport
          </Command.Item>
          <Command.Item
            value="action changer de thème clair sombre"
            onSelect={() => {
              setChoice(theme === "dark" ? "light" : "dark");
              setOpen(false);
            }}
            className={itemClass}
          >
            {theme === "dark" ? <Sun className="h-4 w-4 text-slate-400" aria-hidden="true" /> : <Moon className="h-4 w-4 text-slate-400" aria-hidden="true" />}
            {theme === "dark" ? "Thème clair" : "Thème sombre"}
          </Command.Item>
        </Command.Group>
        {entities.runs.length > 0 && (
          <Command.Group heading="Exécutions récentes" className={groupClass}>
            {entities.runs.map((r) => (
              <Command.Item key={r.id} value={`exécution ${r.label ?? ""} ${r.id}`} onSelect={() => go(`/runs/${r.id}/summary`)} className={itemClass}>
                <History className="h-4 w-4 text-slate-400" aria-hidden="true" />
                <span className="truncate">{r.label || `Exécution ${shortId(r.id)}`}</span>
                <span className="ml-auto text-xs text-slate-500">{fmtDate(r.created_at)}</span>
              </Command.Item>
            ))}
          </Command.Group>
        )}
        {entities.datasets.length > 0 && (
          <Command.Group heading="Données" className={groupClass}>
            {entities.datasets.map((d) => (
              <Command.Item key={d.id} value={`données ${d.name} ${d.id}`} onSelect={() => go(`/datasets/${d.id}`)} className={itemClass}>
                <Database className="h-4 w-4 text-slate-400" aria-hidden="true" />
                <span className="truncate">{d.name}</span>
              </Command.Item>
            ))}
          </Command.Group>
        )}
        {entities.scenarios.length > 0 && (
          <Command.Group heading="Scénarios" className={groupClass}>
            {entities.scenarios.map((s) => (
              <Command.Item key={s.id} value={`scénario ${s.name} ${s.id}`} onSelect={() => go(`/scenarios/${s.id}`)} className={itemClass}>
                <GitBranch className="h-4 w-4 text-slate-400" aria-hidden="true" />
                <span className="truncate">{s.name}</span>
              </Command.Item>
            ))}
          </Command.Group>
        )}
        {entities.reports.length > 0 && (
          <Command.Group heading="Rapports" className={groupClass}>
            {entities.reports.map((r) => (
              <Command.Item key={r.id} value={`rapport ${r.title} ${r.id}`} onSelect={() => go(`/reports/${r.id}`)} className={itemClass}>
                <FileText className="h-4 w-4 text-slate-400" aria-hidden="true" />
                <span className="truncate">{r.title}</span>
              </Command.Item>
            ))}
          </Command.Group>
        )}
      </Command.List>
    </Command.Dialog>
  );
}
