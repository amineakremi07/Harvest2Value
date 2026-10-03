"use client";

import { useState } from "react";
import { Sparkles } from "lucide-react";
import { Button, Card, ErrorBanner } from "@/components/ui/primitives";
import { ApiError, errorMessage } from "@/lib/api/client";
import type { NarrativeResponse } from "@/lib/api/types";
import { AI_DISABLED_TEXT, useAiStatus } from "./useAiStatus";
import { asVerification, VerificationBadge, VerifiedText } from "./VerifiedText";

/** An AI narrative written on demand. Its numbers are rendered and verified by the backend. */
export function NarrativeCard({ title, load, hint }: { title: string; load: () => Promise<NarrativeResponse>; hint: string }) {
  const status = useAiStatus();
  const [narrative, setNarrative] = useState<NarrativeResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function generate() {
    setBusy(true);
    setError(null);
    try {
      setNarrative(await load());
    } catch (err) {
      setError(err instanceof ApiError && err.code === "LLM_NOT_CONFIGURED" ? AI_DISABLED_TEXT : errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const disabled = status === "disabled" || status === "unreachable";
  return (
    <Card
      title={title}
      actions={
        !disabled && (
          <Button onClick={generate} busy={busy}>
            <Sparkles className="h-4 w-4" aria-hidden="true" />
            {narrative ? "Réécrire" : "Rédiger avec l'IA"}
          </Button>
        )
      }
    >
      {disabled ? (
        <p className="text-sm text-slate-400" role="note">
          {status === "disabled" ? AI_DISABLED_TEXT : "Serveur injoignable."}
        </p>
      ) : narrative ? (
        <div className="space-y-2 text-sm text-slate-200" aria-label={title} role="region">
          <VerifiedText text={narrative.text} />
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <VerificationBadge verification={asVerification(narrative.verification)} />
            <span>
              {narrative.model} · {narrative.prompt}
            </span>
          </div>
        </div>
      ) : (
        <p className="flex items-start gap-3 text-sm text-slate-400">
          <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" aria-hidden="true" />
          {hint}
        </p>
      )}
      {error && (
        <div className="mt-3">
          <ErrorBanner message={error} />
        </div>
      )}
    </Card>
  );
}
