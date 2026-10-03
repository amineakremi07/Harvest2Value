"use client";

import { useState, type FormEvent } from "react";
import { Plus, Sparkles } from "lucide-react";
import { Button, ErrorBanner, inputClass } from "@/components/ui/primitives";
import { ApiError, errorMessage } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import type { ChangeInput, ParseResult, ProposedChange } from "@/lib/api/types";
import { AI_DISABLED_TEXT, useAiStatus } from "@/features/copilot/useAiStatus";
import { opLabel } from "./targets";

export function asProposedInput(change: ProposedChange): ChangeInput {
  return { op: change.op, target: change.target ?? null, params: change.params, source: "ai_proposed", note: change.quote ?? null };
}

/**
 * "Et si…" in plain words -> typed changes proposed by the AI, validated by the backend (op,
 * target, values taken from the sentence). Nothing is added until the user clicks "Ajouter".
 */
export function ScenarioTextInput({ scenarioId, onAdd }: { scenarioId: string; onAdd: (change: ChangeInput) => Promise<boolean> }) {
  const status = useAiStatus();
  const [text, setText] = useState("");
  const [result, setResult] = useState<ParseResult | null>(null);
  const [added, setAdded] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    setAdded([]);
    try {
      setResult(await api.parseScenarioText(text.trim(), { scenario_id: scenarioId }));
    } catch (err) {
      setError(err instanceof ApiError && err.code === "LLM_NOT_CONFIGURED" ? AI_DISABLED_TEXT : errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function add(i: number, change: ProposedChange) {
    if (await onAdd(asProposedInput(change))) setAdded((list) => [...list, i]);
  }

  if (status === "disabled") {
    return (
      <p className="text-sm text-slate-400" role="note">
        {AI_DISABLED_TEXT}
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <form onSubmit={submit} className="space-y-2" aria-label="Décrire une modification">
        <textarea
          className={`${inputClass} resize-none`}
          rows={2}
          maxLength={1000}
          placeholder="Ex. : et si le prix de Sfax baisse de 10 % ?"
          aria-label="Modification en langage naturel"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <Button type="submit" busy={busy} disabled={!text.trim()}>
          <Sparkles className="h-4 w-4" aria-hidden="true" />
          Traduire en modifications
        </Button>
      </form>
      {error && <ErrorBanner message={error} />}
      {result && (
        <div className="space-y-2 text-sm" aria-label="Modifications proposées" role="region">
          {result.changes.length === 0 && <p className="text-slate-400">Aucune modification reconnue.</p>}
          {result.changes.map((c, i) => (
            <div key={i} className="flex items-start justify-between gap-2 rounded-lg border border-cyan-500/30 bg-cyan-500/5 p-2">
              <div className="min-w-0">
                <p className="font-semibold text-cyan-200">{opLabel(c.op)}</p>
                <p className="text-slate-300">{c.summary}</p>
                {c.quote && <p className="text-xs text-slate-500">« {c.quote} »</p>}
              </div>
              <Button onClick={() => add(i, c)} disabled={added.includes(i)} aria-label={`Ajouter : ${c.summary}`}>
                <Plus className="h-4 w-4" aria-hidden="true" />
                {added.includes(i) ? "Ajoutée" : "Ajouter"}
              </Button>
            </div>
          ))}
          {result.rejected.map((r, i) => (
            <p key={`r${i}`} className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-2 text-amber-200">
              Écartée ({String(r.change.op ?? "?")}) : {r.reason}
            </p>
          ))}
          {result.questions.map((q, i) => (
            <p key={`q${i}`} className="text-slate-400">
              ? {q}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
