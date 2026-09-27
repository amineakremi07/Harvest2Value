"use client";

import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  Bot,
  Loader2,
  Send,
  Wheat,
  Warehouse,
  TrendingUp,
} from "lucide-react";
import Sidebar from "@/app/components/Sidebar";
import Header from "@/app/components/Header";
import HarvestInput, { type HarvestInputValues } from "@/app/components/HarvestInput";
import AllocationTable from "@/app/components/AllocationTable";
import RiskGauge, { RISK_CONFIG, getRiskLevel, getWasteRatio } from "@/app/components/RiskGauge";
import FlowChart from "@/app/components/FlowChart";
import SankeyChart from "@/app/components/SankeyChart";
import {
  ApiError,
  MOCK_OPTIMIZE_RESPONSE,
  optimizeHarvest,
  type OptimizeRequest,
  type OptimizeResponse,
} from "@/app/lib/api";

type LoadStatus = "idle" | "loading" | "success" | "error";

/**
 * HarvestInput only collects harvest_kg/storage_capacity_kg — buyers are
 * chosen by the optimizer, not entered by the user. The backend's
 * OptimizeRequest schema still requires a non-empty `buyers` list, though,
 * so until Member 1 exposes a buyer directory (or makes buyers optional
 * server-side), we submit a placeholder candidate pool here. The optimizer
 * decides how much (if any) of the harvest each one actually gets.
 */
const DEFAULT_BUYER_POOL = [
  {
    id: "buyer-1",
    name: "Local Cooperative",
    location: "Nearby Market",
    max_demand_kg: 50000,
    price_per_kg: 0.8,
    distance_km: 15,
    transport_cost_per_kg_per_km: 0.01,
  },
  {
    id: "buyer-2",
    name: "Regional Distributor",
    location: "Regional Hub",
    max_demand_kg: 50000,
    price_per_kg: 0.65,
    distance_km: 60,
    transport_cost_per_kg_per_km: 0.008,
  },
];

/**
 * HarvestInput only collects harvest_kg/storage_capacity_kg. The remaining
 * OptimizeRequest fields don't have a form yet, so we fill them with
 * sensible defaults here until a producer identity / crop / logistics form
 * step is added.
 */
function buildOptimizeRequest(values: HarvestInputValues): OptimizeRequest {
  return {
    producer: {
      id: "producer-1",
      name: "My Farm",
      region: "Unknown",
      country: "Unknown",
      harvest_kg: values.harvest_kg,
      storage_capacity_kg: values.storage_capacity_kg,
      shelf_life_days: 14,
    },
    buyers: DEFAULT_BUYER_POOL,
    crop: {
      name: "Mixed Produce",
      type: "semi_perishable",
    },
    logistics: {
      available_vehicles: 1,
      vehicle_capacity_kg: Math.max(values.harvest_kg, 1000),
      refrigerated_required: false,
      road_condition: "fair",
    },
  };
}

const card = "bg-white dark:bg-[#131B2E] border border-slate-200 dark:border-[#1E293B] rounded-xl p-6";

const numberFormatter = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "TND",
  maximumFractionDigits: 0,
});

function KpiCard({
  icon: Icon,
  label,
  value,
  accentColor,
}: {
  icon: typeof Wheat;
  label: string;
  value: string;
  accentColor: string;
}) {
  return (
    <div className={`${card} border-l-4`} style={{ borderLeftColor: accentColor }}>
      <div className="mb-3 flex items-center gap-2 text-[#64748B] dark:text-slate-400">
        <Icon className="h-4 w-4" aria-hidden="true" />
        <span className="text-xs font-semibold uppercase tracking-wider">{label}</span>
      </div>
      <div className="font-mono text-[28px] font-bold tabular-nums text-[#0F172A] dark:text-white">{value}</div>
    </div>
  );
}

interface ChatMessage {
  id: number;
  role: "assistant" | "user";
  text: string;
}

const INITIAL_MESSAGES: ChatMessage[] = [
  {
    id: 1,
    role: "assistant",
    text: "Hello! I am your Dark Eco AI assistant. Ask me anything about your harvest allocations, transport routes, or what-if scenarios (e.g., \u201cWhat if buyer prices drop by 10%?\u201d).",
  },
  {
    id: 2,
    role: "user",
    text: "What if buyer prices drop by 10%?",
  },
];

const QUICK_PROMPTS = [
  { emoji: "\u{1F4A1}", label: "Explain Allocation", prompt: "Explain this allocation." },
  { emoji: "\u{1F4C9}", label: "Price Drop -10%", prompt: "What if buyer prices drop by 10%?" },
  { emoji: "\u{1F69B}", label: "Optimize Routes", prompt: "How can I optimize transport routes?" },
] as const;

/**
 * Chat shell only. Answering a question means calling /api/v1/scenario and
 * /api/v1/explain through Member 3's `UnifiedChat.tsx`, which doesn't exist
 * yet — so sending a message echoes it into the feed and replies with a
 * stub. Swap `PENDING_REPLY` for the real call once that component lands.
 */
const PENDING_REPLY =
  "The assistant backend isn't wired up yet \u2014 @Member3's UnifiedChat.tsx will answer this against /api/v1/scenario and /api/v1/explain.";

function AssistantCard() {
  const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES);
  const [draft, setDraft] = useState("");
  const feedRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const feed = feedRef.current;
    if (feed) {
      feed.scrollTop = feed.scrollHeight;
    }
  }, [messages]);

  function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed) return;

    setMessages((prev) => {
      const nextId = prev.length > 0 ? prev[prev.length - 1].id + 1 : 1;
      return [
        ...prev,
        { id: nextId, role: "user", text: trimmed },
        { id: nextId + 1, role: "assistant", text: PENDING_REPLY },
      ];
    });
    setDraft("");
  }

  return (
    <section
      className={`${card} flex h-full min-h-[420px] flex-col`}
      aria-labelledby="assistant-heading"
    >
      {/* Header */}
      <div className="mb-3 flex items-center justify-between gap-3 border-b border-slate-200 dark:border-[#1E293B] pb-3">
        <div className="flex items-center gap-2 text-[#64748B] dark:text-slate-400">
          <Bot className="h-4 w-4 text-[#059669] dark:text-[#10B981]" aria-hidden="true" />
          <h2 id="assistant-heading" className="text-xs font-semibold uppercase tracking-wider">
            AI Assistant
          </h2>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-[#059669]/30 dark:border-[#10B981]/30 bg-[#059669]/10 dark:bg-[#10B981]/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-[#059669] dark:text-[#10B981]">
          <span className="h-1.5 w-1.5 rounded-full bg-[#059669] dark:bg-[#10B981]" aria-hidden="true" />
          Online
        </span>
      </div>

      {/* Message feed */}
      <div
        ref={feedRef}
        role="log"
        aria-live="polite"
        aria-label="Chat history"
        className="flex-1 space-y-3 overflow-y-auto rounded-lg border border-slate-200 dark:border-[#1E293B] bg-[#F8FAFC]/60 dark:bg-[#0B101D]/60 p-4"
      >
        {messages.map((message) => {
          const isUser = message.role === "user";
          return (
            <div key={message.id} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
              <p
                className={`max-w-[85%] rounded-lg px-3 py-2 text-sm leading-relaxed ${
                  isUser
                    ? "bg-[#E2E8F0] dark:bg-[#1E293B] text-[#0F172A] dark:text-white"
                    : "border border-slate-200 dark:border-[#1E293B] bg-white dark:bg-[#131B2E] text-[#334155] dark:text-slate-300"
                }`}
              >
                {message.text}
              </p>
            </div>
          );
        })}
      </div>

      {/* Quick prompt chips */}
      <div className="mt-3 flex flex-wrap gap-2">
        {QUICK_PROMPTS.map(({ emoji, label, prompt }) => (
          <button
            key={label}
            type="button"
            onClick={() => sendMessage(prompt)}
            className="inline-flex min-h-[36px] items-center gap-1.5 rounded-full border border-slate-200 dark:border-[#1E293B] bg-[#F8FAFC] dark:bg-[#0B101D] px-3 py-1.5 text-xs font-semibold text-[#334155] dark:text-slate-300 hover:border-[#059669]/50 dark:hover:border-[#10B981]/50 hover:text-[#0F172A] dark:hover:text-white focus:outline-none focus:ring-2 focus:ring-[#059669] dark:focus:ring-[#10B981]"
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
          sendMessage(draft);
        }}
      >
        <input
          type="text"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Type a question or what-if scenario..."
          aria-label="Ask the assistant a question"
          className="min-h-[44px] flex-1 rounded-lg border border-slate-200 dark:border-[#1E293B] bg-[#F8FAFC] dark:bg-[#0B101D] px-4 text-sm text-[#0F172A] dark:text-white placeholder:text-[#94A3B8] dark:placeholder:text-slate-500 focus:border-[#059669] dark:focus:border-[#10B981] focus:outline-none focus:ring-1 focus:ring-[#059669] dark:focus:ring-[#10B981]"
        />
        <button
          type="submit"
          disabled={draft.trim().length === 0}
          aria-label="Send message"
          className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-[#059669] dark:bg-[#10B981] text-white dark:text-black hover:bg-emerald-700 dark:hover:bg-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-600 dark:focus:ring-emerald-300 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Send className="h-4 w-4" aria-hidden="true" />
        </button>
      </form>
    </section>
  );
}

export default function Home() {
  const [status, setStatus] = useState<LoadStatus>("idle");
  const [result, setResult] = useState<OptimizeResponse>(MOCK_OPTIMIZE_RESPONSE);
  const [error, setError] = useState<string | null>(null);
  const [usingDemoData, setUsingDemoData] = useState(true);

  async function handleSubmit(values: HarvestInputValues) {
    setStatus("loading");
    setError(null);

    try {
      const response = await optimizeHarvest(buildOptimizeRequest(values));
      setResult(response);
      setUsingDemoData(false);
      setStatus("success");
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Unexpected error running optimization.";
      setError(message);
      setStatus("error");
    }
  }

  function useDemoData() {
    setResult(MOCK_OPTIMIZE_RESPONSE);
    setUsingDemoData(true);
    setError(null);
    setStatus("idle");
  }

  const riskLevel = getRiskLevel(getWasteRatio(result));
  const riskConfig = RISK_CONFIG[riskLevel];

  return (
    <div className="min-h-screen bg-[#F8FAFC] dark:bg-[#090D16] text-[#0F172A] dark:text-white">
      <Sidebar />

      <div className="lg:pl-64">
        <div className="mx-auto max-w-7xl px-6 py-6 lg:px-10">
          <Header />

          <div className="mt-6 space-y-6">
            {status === "loading" && (
              <div className={`${card} flex items-center gap-2 py-3 text-base font-medium`}>
                <Loader2 className="h-5 w-5 animate-spin text-[#059669] dark:text-[#10B981]" aria-hidden="true" />
                <span>Running optimization…</span>
              </div>
            )}

            {status === "error" && error && (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-rose-500/30 bg-rose-500/10 px-6 py-4">
                <span className="inline-flex items-center gap-2 text-base font-medium text-rose-700 dark:text-rose-300">
                  <AlertTriangle className="h-5 w-5" aria-hidden="true" />
                  <span>{error}</span>
                </span>
                <button
                  type="button"
                  onClick={useDemoData}
                  className="inline-flex min-h-[40px] items-center rounded-full bg-[#06B6D4] px-4 py-2 text-sm font-bold text-white dark:text-black hover:bg-cyan-400 focus:outline-none focus:ring-2 focus:ring-cyan-300"
                >
                  Use demo data
                </button>
              </div>
            )}

            {usingDemoData && status !== "loading" && status !== "error" && (
              <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-6 py-4 text-base font-medium text-amber-700 dark:text-amber-300">
                Showing demo data — run an optimization to see your own results.
              </div>
            )}

            {/* KPI metrics row */}
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
              <KpiCard
                icon={Wheat}
                label="Total Harvest"
                value={`${numberFormatter.format(result.total_harvest_kg)} kg`}
                accentColor="#10B981"
              />
              <KpiCard
                icon={Warehouse}
                label="Active Storage"
                value={`${numberFormatter.format(result.stored_kg)} kg`}
                accentColor="#06B6D4"
              />
              <KpiCard
                icon={TrendingUp}
                label="Net Profit"
                value={currencyFormatter.format(result.net_profit)}
                accentColor="#10B981"
              />
              <KpiCard
                icon={riskConfig.icon}
                label="Risk Rating"
                value={riskConfig.label}
                accentColor={riskConfig.ringColor}
              />
            </div>

            {/* Controls row: harvest form + risk summary */}
            <div className="grid grid-cols-12 gap-6">
              <div className="col-span-12 lg:col-span-7">
                <HarvestInput onSubmit={handleSubmit} />
              </div>
              <div className="col-span-12 lg:col-span-5">
                <RiskGauge result={result} />
              </div>
            </div>

            {/*
              Main grid. The left column stacks the allocation table over the
              assistant card, which flexes to absorb whatever vertical space the
              taller right-hand logistics panel leaves behind.
            */}
            <div className="grid grid-cols-12 items-stretch gap-6 lg:min-h-[640px]">
              <div className="col-span-12 flex flex-col gap-6 lg:col-span-7">
                <AllocationTable result={result} />
                <AssistantCard />
              </div>

              <div className="col-span-12 lg:col-span-5">
                <FlowChart result={result} className="h-full" />
              </div>
            </div>

            {/* Harvest -> buyers/storage/waste flow (Member 4), full width */}
            <div className="grid grid-cols-12 gap-6">
              <div className="col-span-12">
                <SankeyChart result={result} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
