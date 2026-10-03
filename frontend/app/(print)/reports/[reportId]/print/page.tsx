import { PrintReport } from "@/features/reports/PrintReport";

export default async function PrintReportPage({ params }: { params: Promise<{ reportId: string }> }) {
  const { reportId } = await params;
  return <PrintReport reportId={reportId} />;
}
