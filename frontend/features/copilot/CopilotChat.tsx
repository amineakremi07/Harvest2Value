"use client";

import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Bot, Loader2, Send, Wrench } from "lucide-react";
import { Button, cx, ErrorBanner, inputClass, Loading } from "@/components/ui/primitives";
import { errorMessage } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import { streamMessage, type CopilotEvent } from "@/lib/api/sse";
import type { ActionView, MessageView, PageContext } from "@/lib/api/types";
import { ActionCard } from "./ActionCard";
import { SUGGESTIONS } from "./pageContext";
import { asVerification, VerificationBadge, VerifiedText } from "./VerifiedText";

type ToolStep = { name: string; ok?: boolean; summary?: string };

export const TOOL_LABEL: Record<string, string> = {
  get_context: "Lecture du contexte",
  get_dataset: "Lecture des données",
  get_market_analysis: "Analyse du marché",
  get_run: "Lecture de l'exécution",
  get_allocations: "Lecture des allocations",
  get_constraints: "Contraintes saturées",
  get_bottlenecks: "Goulots d'étranglement",
  explain_decision: "Explication d'une décision",
  get_insights: "Alertes",
  get_buyer_analysis: "Analyse des acheteurs",
  get_logistics_analysis: "Analyse logistique",
  get_crop_analysis: "Analyse de la culture",
  preview_scenario: "Aperçu de modifications",
  compare_runs: "Comparaison d'exécutions",
  list_change_ops: "Catalogue des modifications",
  create_scenario: "Proposition de scénario",
  run_optimization: "Proposition d'optimisation",
  generate_report: "Proposition de rapport",
};

function Message({ message, actions, onAction }: { message: MessageView; actions: ActionView[]; onAction: (a: ActionView) => void }) {
  if (message.role === "user") {
    return (
      <div className="ml-8 rounded-lg bg-emerald-500/10 px-3 py-2 text-sm text-slate-100" data-role="user">
        {message.content}
      </div>
    );
  }
  if (message.role === "error") {
    return (
      <div className="mr-8 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200" data-role="error">
        {message.content}
      </div>
    );
  }
  const verification = asVerification(message.verification);
  const tools = message.tool_trace ?? [];
  return (
    <div className="mr-4 space-y-2" data-role="assistant">
      <div className="rounded-lg border border-card-border bg-navy-deep px-3 py-2 text-sm text-slate-100">
        <VerifiedText text={message.content} />
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <VerificationBadge verification={verification} />
          {tools.length > 0 && (
            <span title={tools.map((t) => String(t.name)).join(", ")}>
              {tools.length} outil{tools.length > 1 ? "s" : ""} consulté{tools.length > 1 ? "s" : ""}
            </span>
          )}
        </div>
      </div>
      {actions.map((a) => (
        <ActionCard key={a.id} action={a} onChange={onAction} />
      ))}
    </div>
  );
}

/**
 * One copilot conversation. Answers stream (tool activity, then the answer); numbers are rendered
 * by the backend and unverified ones highlighted; proposals appear as cards to confirm.
 */
export function CopilotChat({
  conversationId,
  context,
  onConversation,
  compact = false,
}: {
  conversationId: string | null;
  context: PageContext;
  onConversation: (id: string) => void;
  compact?: boolean;
}) {
  const [messages, setMessages] = useState<MessageView[]>([]);
  const [actions, setActions] = useState<ActionView[]>([]);
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [steps, setSteps] = useState<ToolStep[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [text, setText] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const loadedRef = useRef<string | null>(null);

  useEffect(() => {
    if (!conversationId || loadedRef.current === conversationId) return;
    loadedRef.current = conversationId;
    let live = true;
    setLoading(true);
    api.conversation(conversationId).then(
      (c) => {
        if (!live) return;
        setMessages(c.messages);
        setActions(c.actions);
        setLoading(false);
      },
      (err: unknown) => {
        if (!live) return;
        setError(errorMessage(err));
        setLoading(false);
      },
    );
    return () => {
      live = false;
    };
  }, [conversationId]);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "end" });
  }, [messages, steps]);

  const updateAction = (a: ActionView) => setActions((list) => list.map((x) => (x.id === a.id ? a : x)));

  function onEvent(event: CopilotEvent) {
    switch (event.event) {
      case "user_message":
        setMessages((list) => [...list, event.data]);
        break;
      case "tool_call":
        setSteps((list) => [...list, { name: event.data.name }]);
        break;
      case "tool_result":
        setSteps((list) => {
          const i = list.findIndex((s) => s.name === event.data.name && s.ok === undefined);
          if (i < 0) return list;
          const next = [...list];
          next[i] = { ...next[i], ok: event.data.ok, summary: event.data.summary };
          return next;
        });
        break;
      case "answer":
        setMessages((list) => [...list, event.data.message]);
        setActions((list) => [...list, ...event.data.actions]);
        break;
      case "error":
        setError(event.data.message);
        break;
      default:
        break;
    }
  }

  async function send(content: string) {
    const trimmed = content.trim();
    if (!trimmed || sending) return;
    setSending(true);
    setError(null);
    setSteps([]);
    try {
      let id = conversationId;
      if (!id) {
        const created = await api.createConversation(context);
        id = created.id;
        loadedRef.current = id;
        onConversation(id);
      }
      setText("");
      await streamMessage(id, trimmed, context, onEvent);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSending(false);
      setSteps([]);
    }
  }

  const submit = (e: FormEvent) => {
    e.preventDefault();
    void send(text);
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send(text);
    }
  };

  const byMessage = (id: string) => actions.filter((a) => a.message_id === id);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className={cx("min-h-0 flex-1 space-y-3 overflow-y-auto", compact ? "p-3" : "p-1")} aria-live="polite" aria-label="Messages du Copilot" role="log">
        {loading && <Loading label="Chargement de la conversation…" />}
        {!loading && messages.length === 0 && (
          <div className="space-y-3 text-sm text-slate-400">
            <p className="flex items-start gap-2">
              <Bot className="mt-0.5 h-4 w-4 shrink-0 text-emerald-accent" aria-hidden="true" />
              Posez une question sur vos données, vos exécutions ou vos scénarios. Les chiffres viennent du backend ; toute
              modification vous est proposée avant d&apos;être appliquée.
            </p>
            <ul className="space-y-1">
              {SUGGESTIONS.map((s) => (
                <li key={s}>
                  <button type="button" onClick={() => void send(s)} className="text-left text-cyan-300 hover:underline" disabled={sending}>
                    {s}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {messages.map((m) => (
          <Message key={m.id} message={m} actions={byMessage(m.id)} onAction={updateAction} />
        ))}
        {sending && (
          <div className="mr-8 space-y-1 text-xs text-slate-400" role="status" aria-label="Le Copilot travaille">
            {steps.map((s, i) => (
              <p key={i} className="flex items-center gap-2">
                <Wrench className={cx("h-3 w-3", s.ok === false ? "text-amber-400" : "text-slate-500")} aria-hidden="true" />
                {TOOL_LABEL[s.name] ?? s.name}
                {s.ok === undefined ? "…" : s.ok ? " ✓" : " (échec, nouvel essai)"}
              </p>
            ))}
            <p className="flex items-center gap-2">
              <Loader2 className="h-3 w-3 animate-spin text-emerald-accent" aria-hidden="true" />
              Réflexion…
            </p>
          </div>
        )}
        {error && <ErrorBanner message={error} />}
        <div ref={endRef} />
      </div>
      <form onSubmit={submit} className={cx("flex items-end gap-2 border-t border-card-border", compact ? "p-3" : "pt-3")} aria-label="Écrire au Copilot">
        <textarea
          className={cx(inputClass, "min-h-[42px] resize-none")}
          rows={compact ? 2 : 3}
          placeholder="Votre question…"
          aria-label="Message au Copilot"
          maxLength={4000}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKey}
        />
        <Button type="submit" variant="primary" busy={sending} disabled={!text.trim()} aria-label="Envoyer">
          <Send className="h-4 w-4" aria-hidden="true" />
        </Button>
      </form>
    </div>
  );
}
