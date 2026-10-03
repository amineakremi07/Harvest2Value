import type { ReactNode } from "react";
import { RunShell } from "@/features/optimization/RunShell";

export default async function RunLayout({ children, params }: { children: ReactNode; params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <RunShell runId={id}>{children}</RunShell>;
}
