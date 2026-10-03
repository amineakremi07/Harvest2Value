import { CompareView } from "@/features/compare/CompareView";

type Search = { baseline?: string | string[]; runs?: string | string[] };

export default async function ComparePage({ searchParams }: { searchParams: Promise<Search> }) {
  const { baseline, runs } = await searchParams;
  const runIds = (typeof runs === "string" ? runs : "").split(",").filter(Boolean);
  return <CompareView initialBaseline={typeof baseline === "string" ? baseline : undefined} initialRuns={runIds} />;
}
