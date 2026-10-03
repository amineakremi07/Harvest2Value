import { ReportView } from "@/features/reports/ReportsPages";

export default async function ReportPage({ params }: { params: Promise<{ reportId: string }> }) {
  const { reportId } = await params;
  return <ReportView key={reportId} reportId={reportId} />;
}
