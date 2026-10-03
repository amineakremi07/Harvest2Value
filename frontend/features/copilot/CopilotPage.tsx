"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { MessageSquarePlus, Trash2 } from "lucide-react";
import { Button, Card, cx, ErrorBanner, Loading, PageHeader } from "@/components/ui/primitives";
import { errorMessage } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import { useApi } from "@/lib/hooks/useApi";
import type { PageContext } from "@/lib/api/types";
import { fmtDate } from "@/lib/format";
import { CopilotChat } from "./CopilotChat";
import { AI_DISABLED_TEXT, useAiStatus } from "./useAiStatus";

const PAGE_CONTEXT: PageContext = { page: "/copilot", compare_run_ids: [] };

export function CopilotPage({ initialConversation }: { initialConversation?: string }) {
  const router = useRouter();
  const status = useAiStatus();
  const list = useApi(() => api.conversations(), []);
  const [selected, setSelected] = useState<string | null>(initialConversation ?? null);
  const [chatKey, setChatKey] = useState(selected ?? "new");
  const [error, setError] = useState<string | null>(null);

  const select = (id: string | null) => {
    setSelected(id);
    setChatKey(id ?? `new-${Date.now()}`);
    router.replace(id ? `/copilot?c=${id}` : "/copilot");
  };

  async function remove(id: string) {
    if (!window.confirm("Supprimer cette conversation ?")) return;
    try {
      await api.deleteConversation(id);
      if (selected === id) select(null);
      list.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <>
      <PageHeader
        title="Copilot"
        subtitle="Questions en langage naturel sur vos données, exécutions et scénarios. Chiffres vérifiés par le backend, modifications toujours soumises à confirmation."
        actions={
          <Button variant="primary" onClick={() => select(null)}>
            <MessageSquarePlus className="h-4 w-4" aria-hidden="true" />
            Nouvelle conversation
          </Button>
        }
      />
      {status === "disabled" && (
        <div className="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200" role="note">
          <p className="font-semibold">IA désactivée</p>
          <p className="mt-1 text-amber-100/80">{AI_DISABLED_TEXT}</p>
        </div>
      )}
      {error && (
        <div className="mb-4">
          <ErrorBanner message={error} />
        </div>
      )}
      <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
        <Card title="Conversations">
          {list.loading && !list.data ? (
            <Loading />
          ) : list.error ? (
            <ErrorBanner message={errorMessage(list.error)} onRetry={list.reload} />
          ) : (list.data?.items ?? []).length === 0 ? (
            <p className="text-sm text-slate-400">Aucune conversation.</p>
          ) : (
            <ul className="space-y-1" aria-label="Liste des conversations">
              {list.data?.items.map((c) => (
                <li key={c.id} className="group flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => select(c.id)}
                    aria-current={selected === c.id ? "true" : undefined}
                    className={cx(
                      "min-w-0 flex-1 rounded-lg px-2 py-1.5 text-left text-sm",
                      selected === c.id ? "bg-white/10 text-white" : "text-slate-300 hover:bg-white/5",
                    )}
                  >
                    <span className="block truncate">{c.title}</span>
                    <span className="block text-xs text-slate-500">{fmtDate(c.updated_at)}</span>
                  </button>
                  <Button variant="ghost" onClick={() => remove(c.id)} aria-label={`Supprimer « ${c.title} »`}>
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <section className="flex h-[70vh] min-h-[420px] flex-col rounded-xl border border-card-border bg-card-surface p-4" aria-label="Conversation">
          {status === "disabled" ? (
            <p className="text-sm text-slate-400">Activez une clé LLM pour discuter avec le Copilot.</p>
          ) : (
            <CopilotChat
              key={chatKey}
              conversationId={selected}
              context={PAGE_CONTEXT}
              onConversation={(id) => {
                setSelected(id);
                router.replace(`/copilot?c=${id}`);
                list.reload();
              }}
            />
          )}
        </section>
      </div>
    </>
  );
}
