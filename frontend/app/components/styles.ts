/** Shared class strings for the CRDA flat enterprise card look (see DESIGN.md §2). */
export const glassCard =
  "rounded-2xl border border-card-border bg-card-surface p-5";

export const inputClass =
  "w-full min-h-[40px] rounded-xl border border-card-border bg-app-bg px-3 py-2 text-sm text-text-primary " +
  "placeholder:text-text-secondary outline-none transition-colors hover:border-accent/50 " +
  "focus-visible:ring-2 focus-visible:ring-accent";

export const numberFormatter = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
export const decimalFormatter = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 });
