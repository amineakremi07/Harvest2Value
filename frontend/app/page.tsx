import Link from "next/link";
import { ArrowRight, BarChart3, Sprout, Users, Warehouse, type LucideIcon } from "lucide-react";
import { glassCard } from "@/app/components/styles";

const VALUE_PROPS: ReadonlyArray<{ icon: LucideIcon; title: string; body: string }> = [
  {
    icon: Sprout,
    title: "Waste Reduction",
    body: "Spot spoilage early by crop and delegation, and see which farmers are cutting waste period over period.",
  },
  {
    icon: Warehouse,
    title: "Storage Optimization",
    body: "Monitor silos, cold storage and warehouses against capacity, and allocate harvest where it keeps longest.",
  },
  {
    icon: Users,
    title: "Farmer Analytics",
    body: "Track income and waste trends for every farmer, with an AI assistant that answers What-If questions.",
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-app-bg text-text-primary">
      <header className="mx-auto flex max-w-6xl items-center px-4 py-5 pr-16 sm:px-6">
        <span className="flex items-center gap-2 text-lg font-bold">
          <Sprout className="h-7 w-7 text-accent-text" aria-hidden="true" />
          Harvest2Value
        </span>
      </header>

      <main>
        <section className="mx-auto max-w-4xl px-4 pb-16 pt-12 text-center sm:px-6 sm:pt-20">
          <p className="mb-4 inline-block rounded-full border border-card-border bg-card-surface px-3 py-1 text-xs font-semibold uppercase tracking-wider text-accent-text">
            Enterprise CRDA Regional Platform
          </p>
          <h1 className="text-4xl font-bold leading-tight sm:text-5xl">
            Harvest2Value — Enterprise Regional Agricultural Optimization
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg text-text-secondary">
            Empowering CRDA administrators to eliminate harvest waste, optimize storage allocation,
            and maximize regional farmer revenue.
          </p>
          <Link
            href="/auth/login"
            className="mt-8 inline-flex min-h-[48px] items-center gap-2 rounded-full bg-accent px-7 py-3 text-base font-bold text-white outline-none transition-colors hover:bg-accent-hover focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-bg"
          >
            Access CRDA Portal
            <ArrowRight className="h-5 w-5" aria-hidden="true" />
          </Link>
        </section>

        <section aria-label="Platform benefits" className="mx-auto grid max-w-6xl gap-4 px-4 pb-20 sm:grid-cols-3 sm:px-6">
          {VALUE_PROPS.map(({ icon: Icon, title, body }) => (
            <div key={title} className={glassCard}>
              <span className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-accent/10 text-accent-text">
                <Icon className="h-5 w-5" aria-hidden="true" />
              </span>
              <h2 className="text-base font-bold">{title}</h2>
              <p className="mt-1 text-sm text-text-secondary">{body}</p>
            </div>
          ))}
        </section>
      </main>

      <footer className="border-t border-card-border py-6 text-center text-xs text-text-secondary">
        <BarChart3 className="mr-1 inline h-3.5 w-3.5" aria-hidden="true" />
        Harvest2Value · Commissariat Régional au Développement Agricole
      </footer>
    </div>
  );
}
