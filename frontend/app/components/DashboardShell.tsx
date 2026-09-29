"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import Header from "@/app/components/Header";
import Sidebar from "@/app/components/Sidebar";
import { logout, useHydrated, useIsAuthenticated } from "@/app/lib/auth";

/**
 * Persistent frame for every authenticated route: sidebar + header, plus the
 * auth guard. Signed-out visitors are sent to /auth/login; Log Out goes to `/`.
 */
export default function DashboardShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const hydrated = useHydrated();
  const authenticated = useIsAuthenticated();
  // Log Out clears auth *and* navigates home; without this flag the guard's
  // own redirect to /auth/login would race that navigation and win.
  const loggingOut = useRef(false);

  useEffect(() => {
    if (hydrated && !authenticated && !loggingOut.current) router.replace("/auth/login");
  }, [hydrated, authenticated, router]);

  function handleLogout() {
    loggingOut.current = true;
    logout();
    router.replace("/");
  }

  if (!hydrated || !authenticated) {
    return (
      <div role="status" className="flex min-h-screen items-center justify-center gap-2 text-text-secondary">
        <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
        <span>Checking session…</span>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-app-bg text-text-primary">
      <Sidebar onLogout={handleLogout} />
      <div className="min-w-0 flex-1">
        <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-10">
          <Header />
          <main className="mt-6 space-y-6">{children}</main>
        </div>
      </div>
    </div>
  );
}
