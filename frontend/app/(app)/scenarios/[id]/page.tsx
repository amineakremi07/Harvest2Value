import { ScenarioStudio } from "@/features/scenarios/ScenarioStudio";

export default async function ScenarioPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ScenarioStudio key={id} scenarioId={id} />;
}
