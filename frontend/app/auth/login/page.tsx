"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import AuthShell from "@/app/components/AuthShell";
import { inputClass } from "@/app/components/styles";
import { beginLogin } from "@/app/lib/auth";

const label = "mb-1 block text-xs font-semibold text-text-secondary";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [delegationId, setDelegationId] = useState("");
  const [agentCode, setAgentCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) return setError("Enter your official CRDA email address.");
    if (!delegationId.trim()) return setError("Delegation ID is required.");
    if (!agentCode.trim()) return setError("Agent code is required.");

    setError(null);
    // Demo: credentials are not verified. Only the email and delegation are kept.
    beginLogin({ email: email.trim(), delegationId: delegationId.trim() });
    router.push("/auth/2fa");
  }

  return (
    <AuthShell title="CRDA Agent Sign In" subtitle="Enter your agent credentials to access the regional portal.">
      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <div>
          <label htmlFor="email" className={label}>Official email</label>
          <input id="email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} className={inputClass} placeholder="agent@crda.example" />
        </div>
        <div>
          <label htmlFor="delegation-id" className={label}>Delegation ID</label>
          <input id="delegation-id" value={delegationId} onChange={(e) => setDelegationId(e.target.value)} className={inputClass} placeholder="e.g. MRN-01" />
        </div>
        <div>
          <label htmlFor="agent-code" className={label}>Agent code</label>
          <input id="agent-code" type="password" autoComplete="current-password" value={agentCode} onChange={(e) => setAgentCode(e.target.value)} className={inputClass} />
        </div>

        {error && (
          <p role="alert" className="rounded-xl border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
            {error}
          </p>
        )}

        <button
          type="submit"
          className="inline-flex min-h-[44px] w-full items-center justify-center rounded-full bg-accent px-6 py-2.5 text-sm font-bold text-white outline-none transition-colors hover:bg-accent-hover focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-bg"
        >
          Continue
        </button>
        <p className="text-center text-xs text-text-secondary">
          Demo mode: credentials are not checked, and any 6-digit code passes verification.
        </p>
      </form>
    </AuthShell>
  );
}
