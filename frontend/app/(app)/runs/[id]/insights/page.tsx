import { RunInsightsPanel } from "@/features/insights/RunInsightsPanel";

export default async function RunInsightsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <RunInsightsPanel runId={id} />;
}
