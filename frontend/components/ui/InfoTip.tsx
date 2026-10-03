"use client";

import { useId, useState, type ReactNode } from "react";
import { Info } from "lucide-react";

/** Small "i" button that shows an explanation on hover, focus or click (accessible tooltip). */
export function InfoTip({ label, children }: { label: string; children: ReactNode }) {
  const id = useId();
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-flex align-middle">
      <button
        type="button"
        aria-label={label}
        aria-describedby={open ? id : undefined}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="rounded-full text-slate-500 hover:text-slate-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-accent"
      >
        <Info className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
      {open && (
        <span
          id={id}
          role="tooltip"
          className="absolute bottom-full left-1/2 z-20 mb-2 w-64 -translate-x-1/2 rounded-lg border border-card-border bg-sidebar-surface p-3 text-xs font-normal normal-case leading-relaxed tracking-normal text-slate-300 shadow-xl"
        >
          {children}
        </span>
      )}
    </span>
  );
}
