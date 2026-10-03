import Link from "next/link";
import { Lightbulb, Trophy, Waypoints } from "lucide-react";
import { Card, EmptyState } from "@/components/ui/primitives";
import { fmtKg, fmtMoney } from "@/lib/format";
import type { DashboardData } from "@/lib/api/types";

/** Deterministic recommendations: opportunities, the main bottleneck and the best buyer. */
export function TopRecommendations({ data }: { data: DashboardData }) {
  const opportunities = data.top_insights.filter((i) => i.category === "opportunity" || i.suggested_changes.length > 0);
  const items: { key: string; icon: typeof Lightbulb; text: string; href?: string }[] = [];

  if (data.main_bottleneck) {
    items.push({
      key: "bottleneck",
      icon: Waypoints,
      text: `Goulot principal : ${data.main_bottleneck.label}${
        data.main_bottleneck.suggested_label ? ` — piste : ${data.main_bottleneck.suggested_label}` : ""
      }`,
      href: `/runs/${data.run.run_id}/explain`,
    });
  }
  for (const i of opportunities.slice(0, 3)) {
    items.push({ key: i.id, icon: Lightbulb, text: i.message, href: `/runs/${i.run_id}/insights` });
  }
  if (data.best_buyer) {
    items.push({
      key: "best-buyer",
      icon: Trophy,
      text: `Meilleur acheteur : ${data.best_buyer.buyer_name} (${fmtKg(data.best_buyer.sold_kg)}, revenu net ${fmtMoney(data.best_buyer.net_revenue)})`,
    });
  }

  return (
    <Card title="Recommandations">
      {items.length === 0 ? (
        <EmptyState title="Rien à recommander pour l'instant." />
      ) : (
        <ul className="space-y-3">
          {items.map(({ key, icon: Icon, text, href }) => (
            <li key={key} className="flex gap-3 text-sm text-slate-200">
              <Icon className="mt-0.5 h-4 w-4 shrink-0 text-emerald-accent" aria-hidden="true" />
              {href ? (
                <Link href={href} className="hover:underline">
                  {text}
                </Link>
              ) : (
                <span>{text}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
