import type { ReactNode } from "react";
import DashboardShell from "@/app/components/DashboardShell";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return <DashboardShell>{children}</DashboardShell>;
}
