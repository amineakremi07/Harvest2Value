"use client";

import { useEffect, useRef, useState } from "react";
import { Bot, Loader2, Send } from "lucide-react";
import {
  API_ORIGIN,
  ApiError,
  sendChatMessage,
  type ChatMessage,
  type OptimizeRequest,
  type OptimizeResponse,
} from "@/app/lib/api";

interface Bubble {
  id: number;
  role: "assistant" | "user";
  text: string;
  isError?: boolean;
}

const GREETING =
  "Hello! I am your AI assistant. Ask me anything about your harvest allocations, transport routes, or what-if scenarios (e.g., “What if buyer prices drop by 10%?”).";

const QUICK_PROMPTS = [
  { emoji: "\u{1F4A1}", label: "Explain Allocation", prompt: "Explain this allocation." },
  { emoji: "\u{1F4C9}", label: "Price Drop -10%", prompt: "What if buyer prices drop by 10%?" },
  { emoji: "\u{1F69B}", label: "Optimize Routes", prompt: "How can I optimize transport routes?" },
] as const;

/** Only the tail of the conversation is replayed to the model each turn. */
const HISTORY_TURNS = 10;

/**
 * FastAPI reports failures as `{ "detail": "..." }`, which `postJson` parses
 * into `ApiError.cause`. Use the server's own wording when it is there, and
 * fall back to something the user can act on when it isn't.
 */
function describeError(err: unknown): string {
  if (!(err instanceof ApiError)) {
    return "Something went wrong talking to the assistant. Please try again.";
  }

  const detail =
    typeof err.cause === "object" && err.cause !== null && "detail" in err.cause
      ? (err.cause as { detail?: unknown }).detail
      : undefined;
  const serverMessage = typeof detail === "string" ? detail : undefined;

  if (err.status === undefined) {
    return `Can't reach the backend at ${API_ORIGIN}. Start it with "uvicorn app.main:app --reload --port 8000", then try again.`;
  }
  if (err.status === 422) {
    return serverMessage ?? "I couldn't apply that scenario — try naming a buyer and a number.";
  }
  if (err.status === 503) {
    return (
      serverMessage ?? "The AI service isn't configured on the backend — its API key is missing."
    );
  }
  if (err.status >= 500) {
    return serverMessage ?? "The assistant couldn't answer that one. Try rephrasing the question.";
  }
  return serverMessage ?? `The assistant returned an error (HTTP ${err.status}).`;
}

export interface UnifiedChatProps {
  /** Dataset the current plan was solved on — sent as `data` on every turn. */
  data: OptimizeRequest;
  /** Current plan, so the assistant can compare before/after on a What-If. */
  result: OptimizeResponse | null;
  /** Called when a What-If returns a re-solved plan, so the dashboard follows. */
  onScenarioResult?: (result: OptimizeResponse, data: Record<string, unknown>) => void;
  className?: string;
}

export default function UnifiedChat({
  data,
  result,
  onScenarioResult,
  className = "",
}: UnifiedChatProps) {
  const [bubbles, setBubbles] = useState<Bubble[]>([
    { id: 1, role: "assistant", text: GREETING },
  ]);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const feedRef = useRef<HTMLDivElement>(null);
  const nextId = useRef(2);

  useEffect(() => {
    const feed = feedRef.current;
    if (feed) {
      feed.scrollTop = feed.scrollHeight;
    }
  }, [bubbles, pending]);

  function append(bubble: Omit<Bubble, "id">) {
    setBubbles((prev) => [...prev, { ...bubble, id: nextId.current++ }]);
  }

  async function send(text: string) {
    const message = text.trim();
    if (!message || pending) return;

    // Error bubbles are UI-only; the model never sees them.
    const history: ChatMessage[] = bubbles
      .filter((bubble) => !bubble.isError)
      .slice(-HISTORY_TURNS)
      .map((bubble) => ({ role: bubble.role, content: bubble.text }));

    append({ role: "user", text: message });
    setDraft("");
    setPending(true);

    try {
      const response = await sendChatMessage({
        message,
        data: data as unknown as Record<string, unknown>,
        result: result as unknown as Record<string, unknown> | null,
        history,
      });

      append({ role: "assistant", text: response.message });

      if (response.type === "what_if" && response.result) {
        onScenarioResult?.(response.result, response.data ?? {});
      }
    } catch (err) {
      append({ role: "assistant", text: describeError(err), isError: true });
    } finally {
      setPending(false);
    }
  }

  return (
    <section
      className={`flex h-full min-h-[420px] flex-col rounded-xl border border-slate-200 bg-white p-6 dark:border-[#1E293B] dark:bg-[#131B2E] ${className}`}
      aria-labelledby="assistant-heading"
    >
      {/* Header */}
      <div className="mb-3 flex items-center justify-between gap-3 border-b border-slate-200 pb-3 dark:border-[#1E293B]">
        <div className="flex items-center gap-2 text-[#64748B] dark:text-slate-400">
          <Bot className="h-4 w-4 text-[#059669] dark:text-[#10B981]" aria-hidden="true" />
          <h2 id="assistant-heading" className="text-xs font-semibold uppercase tracking-wider">
            AI Assistant
          </h2>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-[#059669]/30 bg-[#059669]/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-[#059669] dark:border-[#10B981]/30 dark:bg-[#10B981]/10 dark:text-[#10B981]">
          <span
            className="h-1.5 w-1.5 rounded-full bg-[#059669] dark:bg-[#10B981]"
            aria-hidden="true"
          />
          Online
        </span>
      </div>

      {/* Message feed */}
      <div
        ref={feedRef}
        role="log"
        aria-live="polite"
        aria-busy={pending}
        aria-label="Chat history"
        className="flex-1 space-y-3 overflow-y-auto rounded-lg border border-slate-200 bg-[#F8FAFC] p-4 dark:border-[#1E293B] dark:bg-[#0B101D]/60"
      >
        {bubbles.map((bubble) => {
          const isUser = bubble.role === "user";
          const tone = bubble.isError
            ? "border border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-300"
            : isUser
              ? "bg-[#E2E8F0] text-[#0F172A] dark:bg-[#1E293B] dark:text-white"
              : "border border-slate-200 bg-white text-[#334155] dark:border-[#1E293B] dark:bg-[#131B2E] dark:text-slate-300";
          return (
            <div key={bubble.id} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
              <p
                className={`max-w-[85%] whitespace-pre-line rounded-lg px-3 py-2 text-sm leading-relaxed ${tone}`}
              >
                {bubble.text}
              </p>
            </div>
          );
        })}

        {pending && (
          <div className="flex justify-start">
            <p className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-[#64748B] dark:border-[#1E293B] dark:bg-[#131B2E] dark:text-slate-400">
              <Loader2
                className="h-4 w-4 animate-spin text-[#059669] dark:text-[#10B981]"
                aria-hidden="true"
              />
              <span>Thinking&hellip;</span>
            </p>
          </div>
        )}
      </div>

      {/* Quick prompt chips */}
      <div className="mt-3 flex flex-wrap gap-2">
        {QUICK_PROMPTS.map(({ emoji, label, prompt }) => (
          <button
            key={label}
            type="button"
            onClick={() => send(prompt)}
            disabled={pending}
            className="inline-flex min-h-[36px] items-center gap-1.5 rounded-full border border-slate-200 bg-[#F8FAFC] px-3 py-1.5 text-xs font-semibold text-[#334155] hover:border-[#059669]/50 hover:text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#059669] disabled:cursor-not-allowed disabled:opacity-50 dark:border-[#1E293B] dark:bg-[#0B101D] dark:text-slate-300 dark:hover:border-[#10B981]/50 dark:hover:text-white dark:focus:ring-[#10B981]"
          >
            <span aria-hidden="true">{emoji}</span>
            <span>{label}</span>
          </button>
        ))}
      </div>

      {/* Input row */}
      <form
        className="mt-3 flex items-center gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          send(draft);
        }}
      >
        <input
          type="text"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          disabled={pending}
          placeholder="Type a question or what-if scenario..."
          aria-label="Ask the assistant a question"
          className="min-h-[44px] flex-1 rounded-lg border border-slate-200 bg-[#F8FAFC] px-4 text-sm text-[#0F172A] placeholder:text-[#94A3B8] focus:border-[#059669] focus:outline-none focus:ring-1 focus:ring-[#059669] disabled:opacity-60 dark:border-[#1E293B] dark:bg-[#0B101D] dark:text-white dark:placeholder:text-slate-500 dark:focus:border-[#10B981] dark:focus:ring-[#10B981]"
        />
        <button
          type="submit"
          disabled={pending || draft.trim().length === 0}
          aria-label="Send message"
          className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-[#059669] text-white hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-600 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-[#10B981] dark:text-black dark:hover:bg-emerald-400 dark:focus:ring-emerald-300"
        >
          {pending ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <Send className="h-4 w-4" aria-hidden="true" />
          )}
        </button>
      </form>
    </section>
  );
}
