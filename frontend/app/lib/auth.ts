"use client";

// Mock CRDA agent authentication. There is no backend auth yet: credentials are
// never checked and any 6-digit code passes 2FA. Only the flag below gates the
// dashboard routes, so this is a UX flow, not a security boundary.

import { useMemo, useSyncExternalStore } from "react";

const AUTH_KEY = "h2v.isAuthenticated"; // localStorage: "true" when signed in
const AGENT_KEY = "h2v.agent"; // localStorage: signed-in agent profile (JSON)
const PENDING_KEY = "h2v.pendingAgent"; // sessionStorage: between login and 2FA
const CHANGE_EVENT = "h2v-auth-change";

export interface AgentProfile {
  email: string;
  delegationId: string;
}

function read(store: "local" | "session", key: string): string | null {
  try {
    return (store === "local" ? window.localStorage : window.sessionStorage).getItem(key);
  } catch {
    return null; // storage blocked (private mode, etc.)
  }
}

function write(store: "local" | "session", key: string, value: string | null): void {
  try {
    const s = store === "local" ? window.localStorage : window.sessionStorage;
    if (value === null) s.removeItem(key);
    else s.setItem(key, value);
  } catch {
    // ignore: the flow simply won't persist
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener(CHANGE_EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(CHANGE_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

function parseAgent(raw: string | null): AgentProfile | null {
  if (!raw) return null;
  try {
    const value: unknown = JSON.parse(raw);
    if (
      typeof value === "object" &&
      value !== null &&
      typeof (value as AgentProfile).email === "string" &&
      typeof (value as AgentProfile).delegationId === "string"
    ) {
      return value as AgentProfile;
    }
  } catch {
    // fall through
  }
  return null;
}

// ---- Actions ----

/** Login step 1: remember who is signing in until the 2FA code is entered. */
export function beginLogin(agent: AgentProfile): void {
  write("session", PENDING_KEY, JSON.stringify(agent));
}

/** Login step 2: any 6-digit code is accepted (simulated email verification). */
export function verifyCode(code: string): boolean {
  if (!/^\d{6}$/.test(code)) return false;
  const pending = parseAgent(read("session", PENDING_KEY));
  if (!pending) return false;
  write("local", AGENT_KEY, JSON.stringify(pending));
  write("local", AUTH_KEY, "true");
  write("session", PENDING_KEY, null);
  return true;
}

export function logout(): void {
  write("local", AUTH_KEY, null);
  write("local", AGENT_KEY, null);
  write("session", PENDING_KEY, null);
}

// ---- Hooks ----

/** False on the server and during hydration, true afterwards. */
export function useHydrated(): boolean {
  return useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
}

export function useIsAuthenticated(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => read("local", AUTH_KEY) === "true",
    () => false,
  );
}

export function useAgent(): AgentProfile | null {
  const raw = useSyncExternalStore(subscribe, () => read("local", AGENT_KEY), () => null);
  return useMemo(() => parseAgent(raw), [raw]);
}

export function usePendingAgent(): AgentProfile | null {
  const raw = useSyncExternalStore(subscribe, () => read("session", PENDING_KEY), () => null);
  return useMemo(() => parseAgent(raw), [raw]);
}
