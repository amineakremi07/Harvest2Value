import { Suspense, type ReactNode } from "react";
import { AppSidebar } from "@/components/shell/AppSidebar";
import { CopilotDrawer } from "@/features/copilot/CopilotDrawer";

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-navy-deep text-white">
      <AppSidebar />
      <main className="lg:pl-60">
        <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-10">{children}</div>
      </main>
      <Suspense fallback={null}>
        <CopilotDrawer />
      </Suspense>
    </div>
  );
}
