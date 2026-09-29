"use client";

import { useEffect, useRef, useState, type ClipboardEvent, type KeyboardEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AuthShell from "@/app/components/AuthShell";
import { usePendingAgent, useHydrated, verifyCode } from "@/app/lib/auth";

const LENGTH = 6;

export default function TwoFactorPage() {
  const router = useRouter();
  const hydrated = useHydrated();
  const pending = usePendingAgent();
  const [digits, setDigits] = useState<string[]>(Array(LENGTH).fill(""));
  const [error, setError] = useState<string | null>(null);
  const [verified, setVerified] = useState(false);
  const inputs = useRef<Array<HTMLInputElement | null>>([]);

  // Arriving without going through /auth/login (or after signing in) is a dead end.
  useEffect(() => {
    if (hydrated && !pending && !verified) router.replace("/auth/login");
  }, [hydrated, pending, verified, router]);

  function submit(code: string) {
    if (verifyCode(code)) {
      setVerified(true);
      router.replace("/dashboard");
    } else {
      setError("That code isn't valid. Enter the 6 digits from your email.");
    }
  }

  function setAt(index: number, value: string) {
    const next = [...digits];
    next[index] = value;
    setDigits(next);
    setError(null);
    if (value && index < LENGTH - 1) inputs.current[index + 1]?.focus();
    if (next.every(Boolean)) submit(next.join(""));
  }

  function handleKeyDown(index: number, e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Backspace" && !digits[index] && index > 0) inputs.current[index - 1]?.focus();
    if (e.key === "ArrowLeft" && index > 0) inputs.current[index - 1]?.focus();
    if (e.key === "ArrowRight" && index < LENGTH - 1) inputs.current[index + 1]?.focus();
  }

  function handlePaste(e: ClipboardEvent<HTMLInputElement>) {
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, LENGTH);
    if (!pasted) return;
    e.preventDefault();
    const next = Array.from({ length: LENGTH }, (_, i) => pasted[i] ?? "");
    setDigits(next);
    setError(null);
    inputs.current[Math.min(pasted.length, LENGTH - 1)]?.focus();
    if (pasted.length === LENGTH) submit(pasted);
  }

  return (
    <AuthShell
      title="Verify your identity"
      subtitle="A verification code was sent to your official CRDA email address."
    >
      {pending && (
        <p className="mb-4 text-sm text-text-secondary">
          Sent to <span className="font-mono text-text-primary">{pending.email}</span>
        </p>
      )}

      <fieldset>
        <legend className="mb-2 text-xs font-semibold text-text-secondary">6-digit code</legend>
        <div className="flex justify-between gap-2">
          {digits.map((d, i) => (
            <input
              key={i}
              ref={(el) => {
                inputs.current[i] = el;
              }}
              value={d}
              onChange={(e) => setAt(i, e.target.value.replace(/\D/g, "").slice(-1))}
              onKeyDown={(e) => handleKeyDown(i, e)}
              onPaste={handlePaste}
              inputMode="numeric"
              autoComplete={i === 0 ? "one-time-code" : "off"}
              maxLength={1}
              aria-label={`Digit ${i + 1} of ${LENGTH}`}
              className="h-14 w-full min-w-0 rounded-xl border border-card-border bg-app-bg text-center font-mono text-xl font-bold tabular-nums text-text-primary outline-none transition-colors focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-accent"
            />
          ))}
        </div>
      </fieldset>

      {error && (
        <p role="alert" className="mt-4 rounded-xl border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
          {error}
        </p>
      )}

      <p className="mt-6 text-center text-xs text-text-secondary">
        Demo mode: any 6-digit code is accepted.{" "}
        <Link href="/auth/login" className="font-semibold text-accent-text underline-offset-2 hover:underline">
          Back to sign in
        </Link>
      </p>
    </AuthShell>
  );
}
