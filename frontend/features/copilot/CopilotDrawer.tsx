"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Bot, Maximize2, MessageSquarePlus, X } from "lucide-react";
import { Button, cx } from "@/components/ui/primitives";
import { CopilotChat } from "./CopilotChat";
import { contextFromLocation } from "./pageContext";
import { AI_DISABLED_TEXT, useAiStatus } from "./useAiStatus";

const STORAGE_KEY = "h2v.copilot.conversation";

function readStored(): string | null {
  try {
    return window.sessionStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function store(id: string | null) {
  try {
    if (id) window.sessionStorage.setItem(STORAGE_KEY, id);
    else window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // storage unavailable: the conversation simply is not remembered
  }
}

/** Copilot drawer available on every page of the app shell, aware of what is on screen. */
export function CopilotDrawer() {
  const pathname = usePathname();
  const search = useSearchParams();
  const status = useAiStatus();
  const [open, setOpen] = useState(false);
  // sessionStorage is read lazily on the client; the server render never shows the id (drawer closed).
  const [conversationId, setConversationId] = useState<string | null>(() => (typeof window === "undefined" ? null : readStored()));
  const [chatKey, setChatKey] = useState(0);
  const context = useMemo(() => contextFromLocation(pathname, new URLSearchParams(search.toString())), [pathname, search]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: globalThis.KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  if (pathname.startsWith("/copilot")) return null;

  const remember = (id: string) => {
    setConversationId(id);
    store(id);
  };
  const restart = () => {
    setConversationId(null);
    store(null);
    setChatKey((k) => k + 1);
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls="copilot-drawer"
        className="fixed bottom-5 right-5 z-40 inline-flex items-center gap-2 rounded-full bg-emerald-accent px-4 py-3 text-sm font-bold text-black shadow-lg shadow-emerald-900/40 hover:bg-emerald-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-accent"
      >
        <Bot className="h-5 w-5" aria-hidden="true" />
        Copilot
      </button>
      <aside
        id="copilot-drawer"
        role="dialog"
        aria-label="Copilot"
        aria-modal="false"
        hidden={!open}
        className={cx(
          "fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-card-border bg-sidebar-surface shadow-2xl",
        )}
      >
        <header className="flex items-center justify-between gap-2 border-b border-card-border px-4 py-3">
          <span className="inline-flex items-center gap-2 font-bold text-white">
            <Bot className="h-5 w-5 text-emerald-accent" aria-hidden="true" />
            Copilot
          </span>
          <div className="flex items-center gap-1">
            <Button variant="ghost" onClick={restart} aria-label="Nouvelle conversation" title="Nouvelle conversation">
              <MessageSquarePlus className="h-4 w-4" aria-hidden="true" />
            </Button>
            <Link
              href={open && conversationId ? `/copilot?c=${conversationId}` : "/copilot"}
              className="rounded-lg p-2 text-slate-300 hover:bg-white/5"
              aria-label="Ouvrir en plein écran"
              title="Ouvrir en plein écran"
            >
              <Maximize2 className="h-4 w-4" aria-hidden="true" />
            </Link>
            <Button variant="ghost" onClick={() => setOpen(false)} aria-label="Fermer le Copilot">
              <X className="h-4 w-4" aria-hidden="true" />
            </Button>
          </div>
        </header>
        {status === "disabled" || status === "unreachable" ? (
          <div className="m-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200" role="note">
            <p className="font-semibold">IA désactivée</p>
            <p className="mt-1 text-amber-100/80">{status === "disabled" ? AI_DISABLED_TEXT : "Le serveur est injoignable."}</p>
          </div>
        ) : open ? (
          <CopilotChat key={chatKey} conversationId={conversationId} context={context} onConversation={remember} compact />
        ) : null}
      </aside>
    </>
  );
}
