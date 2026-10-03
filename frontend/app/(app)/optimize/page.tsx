import { OptimizeStudio } from "@/features/optimization/OptimizeStudio";

export default async function OptimizePage({ searchParams }: { searchParams: Promise<{ dataset?: string | string[] }> }) {
  const { dataset } = await searchParams;
  return <OptimizeStudio initialDatasetId={typeof dataset === "string" ? dataset : undefined} />;
}
