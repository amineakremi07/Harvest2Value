import AssistantChat from "@/app/components/AssistantChat";
import PageTitle from "@/app/components/PageTitle";

export default function AiAssistantPage() {
  return (
    <>
      <PageTitle
        title="AI Assistant"
        subtitle="Ask the Llama-3 assistant about spoilage, storage capacity and What-If scenarios."
      />
      <AssistantChat />
    </>
  );
}
