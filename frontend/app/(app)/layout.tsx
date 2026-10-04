import { Suspense, type ReactNode } from "react";
import { AppSidebar } from "@/components/shell/AppSidebar";
import { CommandPalette } from "@/components/shell/CommandPalette";
import { CopilotDrawer } from "@/features/copilot/CopilotDrawer";

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell min-h-screen bg-navy-deep text-white">
      <a
        href="#main"
        className="sr-only z-50 rounded-lg bg-emerald-accent px-3 py-2 text-sm font-semibold text-black focus:not-sr-only focus:fixed focus:left-3 focus:top-3"
      >
        Aller au contenu
      </a>
      <AppSidebar />
      <main id="main" tabIndex={-1} className="lg:pl-60 focus:outline-none">
        <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-10">{children}</div>
      </main>
      <CommandPalette />
      <Suspense fallback={null}>
        <CopilotDrawer />
      </Suspense>
    </div>
  );
}
