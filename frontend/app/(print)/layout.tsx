import type { ReactNode } from "react";
import "./print.css";

/** Print pages: no app shell, light paper colors, page size and margins from CSS @page. */
export default function PrintLayout({ children }: { children: ReactNode }) {
  return <div className="print-root min-h-screen bg-white text-slate-900">{children}</div>;
}
