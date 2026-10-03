import { CopilotPage } from "@/features/copilot/CopilotPage";

type Search = { c?: string | string[] };

export default async function CopilotRoute({ searchParams }: { searchParams: Promise<Search> }) {
  const { c } = await searchParams;
  return <CopilotPage initialConversation={typeof c === "string" ? c : undefined} />;
}
