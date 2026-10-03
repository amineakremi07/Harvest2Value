import { AlertTriangle, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/primitives";
import type { Verification } from "@/lib/api/types";

/** The backend marks every number it could not verify as ⟦?…⟧ (ai/rendering.py). */
const MARKER = /⟦\?([^⟧]*)⟧/g;

export type Segment = { text: string; unverified: boolean };

export function splitVerified(text: string): Segment[] {
  const out: Segment[] = [];
  let last = 0;
  for (const match of text.matchAll(MARKER)) {
    const start = match.index ?? 0;
    if (start > last) out.push({ text: text.slice(last, start), unverified: false });
    out.push({ text: match[1], unverified: true });
    last = start + match[0].length;
  }
  if (last < text.length) out.push({ text: text.slice(last), unverified: false });
  return out;
}

/** AI text with its numbers as rendered by the backend; unverified ones are highlighted, never hidden. */
export function VerifiedText({ text }: { text: string }) {
  return (
    <p className="whitespace-pre-wrap break-words">
      {splitVerified(text).map((s, i) =>
        s.unverified ? (
          <mark
            key={i}
            data-unverified="true"
            title="Chiffre non vérifié : il ne provient d'aucun résultat du backend"
            className="rounded bg-amber-500/20 px-0.5 text-amber-200 underline decoration-dotted"
          >
            {s.text}
          </mark>
        ) : (
          <span key={i}>{s.text}</span>
        ),
      )}
    </p>
  );
}

export function asVerification(value: unknown): Verification | null {
  if (typeof value !== "object" || value === null || !("status" in value)) return null;
  return value as Verification;
}

export function VerificationBadge({ verification }: { verification: Verification | null }) {
  if (!verification) return null;
  if (verification.status === "verified") {
    return (
      <Badge tone="success" title={`${verification.checked_numbers} chiffre(s) contrôlé(s) par le backend`}>
        <ShieldCheck className="h-3 w-3" aria-hidden="true" />
        Chiffres vérifiés
      </Badge>
    );
  }
  const count = verification.unverified_numbers.length + verification.unknown_refs.length;
  return (
    <Badge tone="warning" title="Ces valeurs ne proviennent d'aucun résultat du backend : ne vous y fiez pas.">
      <AlertTriangle className="h-3 w-3" aria-hidden="true" />
      {count} chiffre{count > 1 ? "s" : ""} non vérifié{count > 1 ? "s" : ""}
    </Badge>
  );
}
