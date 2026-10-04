import { DatasetEditor } from "@/features/datasets/DatasetEditor";

type Search = { imported?: string | string[] };

export default async function DatasetPage({ params, searchParams }: { params: Promise<{ datasetId: string }>; searchParams: Promise<Search> }) {
  const { datasetId } = await params;
  const { imported } = await searchParams;
  return <DatasetEditor key={datasetId} datasetId={datasetId} importedFrom={typeof imported === "string" ? imported : undefined} />;
}
