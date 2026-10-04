import { DatasetsIndex } from "@/features/datasets/DatasetsIndex";

type Search = { import?: string | string[] };

export default async function DatasetsPage({ searchParams }: { searchParams: Promise<Search> }) {
  const { import: openImport } = await searchParams;
  return <DatasetsIndex openImport={openImport === "1"} />;
}
