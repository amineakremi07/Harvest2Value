import Link from "next/link";
import { Sprout } from "lucide-react";
import type { ReactNode } from "react";
import { glassCard } from "@/app/components/styles";

/** Centered card frame shared by the login and 2FA screens. */
export default function AuthShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-app-bg px-4 py-16">
      <div className="w-full max-w-md">
        <Link
          href="/"
          className="mb-6 inline-flex items-center gap-2 rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          <Sprout className="h-7 w-7 text-accent-text" aria-hidden="true" />
          <span className="text-lg font-bold text-text-primary">Harvest2Value</span>
        </Link>
        <div className={`${glassCard} p-6 sm:p-8`}>
          <h1 className="text-2xl font-bold text-text-primary">{title}</h1>
          <p className="mt-1 mb-6 text-sm text-text-secondary">{subtitle}</p>
          {children}
        </div>
      </div>
    </div>
  );
}
