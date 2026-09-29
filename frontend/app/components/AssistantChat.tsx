"use client";

import { useEffect, useRef, useState } from "react";
import { Bot, Loader2, MessageSquarePlus, Send } from "lucide-react";
import { describeError } from "@/app/components/UnifiedChat";
import { useDelegation } from "@/app/context/DelegationProvider";
import { sendChatMessage, type ChatMessage } from "@/app/lib/api";
import { buildOptimizeRequest } from "@/app/lib/optimize";
import { computeRegionStats } from "@/app/lib/regionStats";

interface Bubble {
  id: number;
  role: "assistant" | "user";
  text: string;
  isError?: boolean;
}

interface PastChat {
  id: string;
  title: string;
  messages: Array<Pick<Bubble, "role" | "text">>;
}

/** Sample transcripts until the backend stores conversations. */
const PAST_CHATS: PastChat[] = [
  {
    id: "mornag-spoilage",
    title: "Yesterday: Mornag Spoilage Analysis",
    messages: [
      { role: "user", text: "Where is spoilage highest in Mornag this quarter?" },
      {
        role: "assistant",
        text: "Tomatoes account for most of the waste in Mornag. They are the most perishable crop and are stored the shortest time before sale. Moving them into cold storage first is the quickest way to cut losses.",
      },
    ],
  },
  {
    id: "tomato-storage",
    title: "3 days ago: Tomato Storage Optimization",
    messages: [
      { role: "user", text: "How should we allocate tomato harvest across storage?" },
      {
        role: "assistant",
        text: "Fill cold storage with tomatoes before other crops, and keep durable crops such as wheat in silos. That leaves refrigerated space for the produce that spoils fastest.",
      },
    ],
  },
  {
    id: "kelibia-citrus",
    title: "Last week: Kelibia Citrus Capacity Review",
    messages: [
      { role: "user", text: "Is Kelibia short on citrus storage?" },
      {
        role: "assistant",
        text: "The Kelibia citrus cold store is the fullest facility in the delegation. Diverting part of the harvest to the port warehouse would relieve it.",
      },
    ],
  },
];

const HISTORY_TURNS = 10;

const PROMPT_CHIPS = [
  "Which storage facility has the highest capacity risk?",
  "Which crop has the most waste this quarter?",
  "What if buyer prices drop by 10%?",
  "Explain this allocation.",
];

const GREETING =
  "Hello! I'm the CRDA assistant. Ask about storage capacity, spoilage, or What-If scenarios for the selected delegation.";

export default function AssistantChat() {
  const { selected, farmers, facilities } = useDelegation();
  const [bubbles, setBubbles] = useState<Bubble[]>([{ id: 0, role: "assistant", text: GREETING }]);
  const [activeId, setActiveId] = useState<string>("new");
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const feedRef = useRef<HTMLDivElement>(null);
  const nextId = useRef(1);

  useEffect(() => {
    const feed = feedRef.current;
    if (feed) feed.scrollTop = feed.scrollHeight;
  }, [bubbles, pending]);

  function append(bubble: Omit<Bubble, "id">) {
    setBubbles((prev) => [...prev, { ...bubble, id: nextId.current++ }]);
  }

  function openChat(chat: PastChat | null) {
    setActiveId(chat?.id ?? "new");
    const source = chat ? chat.messages : [{ role: "assistant" as const, text: GREETING }];
    setBubbles(source.map((m) => ({ ...m, id: nextId.current++ })));
  }

  async function send(text: string) {
    const message = text.trim();
    if (!message || pending) return;

    const history: ChatMessage[] = bubbles
      .filter((b) => !b.isError)
      .slice(-HISTORY_TURNS)
      .map((b) => ({ role: b.role, content: b.text }));

    append({ role: "user", text: message });
    setDraft("");
    setPending(true);

    // The backend chat endpoint takes an optimizer dataset (see UnifiedChat), so
    // the delegation is sent as one: its total harvest and storage capacity.
    // Farmer-level context needs a backend change (flag to the backend engineer).
    const stats = computeRegionStats(farmers, facilities);
    const data = buildOptimizeRequest(
      {
        harvest_kg: Math.max(stats.totalYieldKg, 1),
        storage_capacity_kg: Math.max(stats.maxKg, 1),
      },
      { name: `${selected.name} delegation`, region: selected.name },
    );

    try {
      const response = await sendChatMessage({
        message,
        data: data as unknown as Record<string, unknown>,
        result: null,
        history,
      });
      append({ role: "assistant", text: response.message });
    } catch (err) {
      append({ role: "assistant", text: describeError(err), isError: true });
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="grid min-h-[520px] gap-4 lg:h-[calc(100vh-15rem)] lg:grid-cols-[280px_1fr]">
      {/* Previous chats */}
      <aside aria-label="Previous chats" className="flex flex-col rounded-2xl border border-card-border bg-card-surface p-4">
        <button
          type="button"
          onClick={() => openChat(null)}
          className="mb-4 inline-flex min-h-[40px] items-center justify-center gap-2 rounded-full bg-accent px-4 py-2 text-sm font-bold text-white outline-none transition-colors hover:bg-accent-hover focus-visible:ring-2 focus-visible:ring-accent"
        >
          <MessageSquarePlus className="h-4 w-4" aria-hidden="true" />
          New chat
        </button>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-secondary">
          Previous chats <span className="normal-case">(sample)</span>
        </h2>
        <ul className="space-y-1 overflow-y-auto">
          {PAST_CHATS.map((chat) => (
            <li key={chat.id}>
              <button
                type="button"
                onClick={() => openChat(chat)}
                aria-current={activeId === chat.id ? "true" : undefined}
                className={`w-full rounded-xl px-3 py-2 text-left text-sm outline-none transition-colors focus-visible:ring-2 focus-visible:ring-accent ${
                  activeId === chat.id
                    ? "bg-accent/10 font-semibold text-accent-text"
                    : "text-text-secondary hover:bg-accent/5 hover:text-text-primary"
                }`}
              >
                {chat.title}
              </button>
            </li>
          ))}
        </ul>
      </aside>

      {/* Conversation */}
      <section aria-label="AI assistant conversation" className="flex min-h-0 flex-col rounded-2xl border border-card-border bg-card-surface p-4">
        <div className="mb-3 flex items-center justify-between gap-3 border-b border-card-border pb-3">
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-accent-text" aria-hidden="true" />
            <h2 className="text-sm font-bold text-text-primary">AI Assistant (Llama-3)</h2>
          </div>
          <span className="rounded-full border border-card-border px-2.5 py-1 text-xs font-semibold text-text-secondary">
            Context: {selected.name}
          </span>
        </div>

        <div
          ref={feedRef}
          role="log"
          aria-live="polite"
          aria-busy={pending}
          aria-label="Conversation"
          className="min-h-0 flex-1 space-y-3 overflow-y-auto rounded-xl border border-card-border bg-app-bg p-4"
        >
          {bubbles.map((b) => {
            const isUser = b.role === "user";
            const tone = b.isError
              ? "border border-danger/40 bg-danger/10 text-danger"
              : isUser
                ? "bg-accent text-white"
                : "border border-card-border bg-card-surface text-text-primary";
            return (
              <div key={b.id} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
                <p className={`max-w-[85%] whitespace-pre-line rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${tone}`}>
                  {b.text}
                </p>
              </div>
            );
          })}
          {pending && (
            <div className="flex justify-start">
              <p className="inline-flex items-center gap-2 rounded-2xl border border-card-border bg-card-surface px-4 py-2.5 text-sm text-text-secondary">
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                Thinking…
              </p>
            </div>
          )}
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          {PROMPT_CHIPS.map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => send(prompt)}
              disabled={pending}
              className="rounded-full border border-card-border bg-app-bg px-3 py-1.5 text-xs font-semibold text-text-secondary outline-none transition-colors hover:border-accent/50 hover:text-text-primary focus-visible:ring-2 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-50"
            >
              {prompt}
            </button>
          ))}
        </div>

        <form
          className="mt-3 flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            send(draft);
          }}
        >
          <input
            type="text"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            disabled={pending}
            placeholder="Ask about storage, spoilage or a What-If scenario..."
            aria-label="Ask the assistant a question"
            className="min-h-[44px] flex-1 rounded-xl border border-card-border bg-app-bg px-4 text-sm text-text-primary outline-none placeholder:text-text-secondary focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-60"
          />
          <button
            type="submit"
            disabled={pending || draft.trim().length === 0}
            aria-label="Send message"
            className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent text-white outline-none transition-colors hover:bg-accent-hover focus-visible:ring-2 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Send className="h-4 w-4" aria-hidden="true" />
          </button>
        </form>
      </section>
    </div>
  );
}
