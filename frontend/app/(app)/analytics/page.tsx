import { AnalyticsCenter } from "@/features/analytics/AnalyticsCenter";

type Search = { run?: string | string[]; compare?: string | string[] };

export default async function AnalyticsPage({ searchParams }: { searchParams: Promise<Search> }) {
  const { run, compare } = await searchParams;
  return (
    <AnalyticsCenter
      initialRun={typeof run === "string" ? run : undefined}
      initialCompare={typeof compare === "string" ? compare : undefined}
    />
  );
}
