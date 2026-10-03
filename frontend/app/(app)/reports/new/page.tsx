import { NewReport } from "@/features/reports/ReportsPages";

type Search = { run?: string | string[] };

export default async function NewReportPage({ searchParams }: { searchParams: Promise<Search> }) {
  const { run } = await searchParams;
  return <NewReport initialRun={typeof run === "string" ? run : undefined} />;
}
