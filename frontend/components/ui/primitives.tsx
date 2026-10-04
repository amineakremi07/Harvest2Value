import type { ButtonHTMLAttributes, ReactNode } from "react";
import { AlertTriangle, Inbox, Loader2 } from "lucide-react";

export function cx(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

export function Card({
  title,
  actions,
  children,
  className,
}: {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cx("min-w-0 rounded-xl border border-card-border bg-card-surface p-4 sm:p-5", className)}>
      {(title || actions) && (
        <header className="mb-4 flex flex-wrap items-center justify-between gap-2">
          {title && <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300">{title}</h2>}
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-2xl font-bold text-white">{title}</h1>
        {subtitle && <div className="mt-1 text-sm text-slate-400">{subtitle}</div>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

type Variant = "primary" | "secondary" | "danger" | "ghost";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-emerald-accent text-black hover:bg-emerald-400",
  secondary: "border border-card-border bg-navy-deep text-slate-200 hover:border-slate-500",
  danger: "border border-rose-500/40 bg-rose-500/10 text-rose-300 hover:bg-rose-500/20",
  ghost: "text-slate-300 hover:bg-white/5",
};

export function Button({
  variant = "secondary",
  busy = false,
  className,
  children,
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; busy?: boolean }) {
  return (
    <button
      type="button"
      {...rest}
      disabled={disabled || busy}
      className={cx(
        "inline-flex min-h-9 items-center justify-center gap-2 rounded-lg px-3 py-1.5 text-sm font-semibold transition-colors",
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-accent disabled:cursor-not-allowed disabled:opacity-50",
        VARIANTS[variant],
        className,
      )}
    >
      {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
      {children}
    </button>
  );
}

export type Tone = "neutral" | "success" | "warning" | "danger" | "info";

const TONES: Record<Tone, string> = {
  neutral: "border-slate-600/50 bg-slate-500/10 text-slate-300",
  success: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  warning: "border-amber-500/40 bg-amber-500/10 text-amber-300",
  danger: "border-rose-500/40 bg-rose-500/10 text-rose-300",
  info: "border-cyan-500/40 bg-cyan-500/10 text-cyan-300",
};

export function Badge({ tone = "neutral", children, title }: { tone?: Tone; children: ReactNode; title?: string }) {
  return (
    <span
      title={title}
      className={cx("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold", TONES[tone])}
    >
      {children}
    </span>
  );
}

export function Loading({ label = "Chargement…" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2 py-6 text-sm text-slate-400">
      <Loader2 className="h-4 w-4 animate-spin text-emerald-accent" aria-hidden="true" />
      {label}
    </div>
  );
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
      <span className="inline-flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
        {message}
      </span>
      {onRetry && (
        <Button variant="ghost" onClick={onRetry}>
          Réessayer
        </Button>
      )}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-card-border px-6 py-10 text-center">
      <Inbox className="h-6 w-6 text-slate-500" aria-hidden="true" />
      <p className="text-sm font-semibold text-slate-300">{title}</p>
      {children && <div className="text-sm text-slate-400">{children}</div>}
    </div>
  );
}

export function Field({ label, hint, children, htmlFor }: { label: string; hint?: ReactNode; children: ReactNode; htmlFor?: string }) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={htmlFor} className="text-xs font-semibold uppercase tracking-wider text-slate-400">
        {label}
      </label>
      {children}
      {hint && <p className="text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

export const inputClass =
  "w-full rounded-lg border border-card-border bg-navy-deep px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:border-cyan-accent focus:outline-none";

export function Table({ children, label }: { children: ReactNode; label?: string }) {
  return (
    <div className="overflow-x-auto">
      <table aria-label={label} className="w-full min-w-max border-collapse text-left text-sm">
        {children}
      </table>
    </div>
  );
}

export const thClass = "border-b border-card-border px-3 py-2 text-xs font-semibold uppercase tracking-wider text-slate-400";
export const tdClass = "border-b border-card-border/60 px-3 py-2 text-slate-200";
export const numClass = "text-right font-mono tabular-nums";
