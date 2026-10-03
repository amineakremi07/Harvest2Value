import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api/endpoints";
import { parseSse, streamMessage, type CopilotEvent } from "@/lib/api/sse";
import type { ActionView, MessageView } from "@/lib/api/types";
import { META } from "@/test/fixtures";
import { ActionCard, resultHref } from "./ActionCard";
import { CopilotChat } from "./CopilotChat";
import { CopilotDrawer } from "./CopilotDrawer";
import { contextFromLocation } from "./pageContext";
import { splitVerified, VerificationBadge, VerifiedText } from "./VerifiedText";

vi.mock("@/lib/api/sse", async (original) => ({ ...(await original<typeof import("@/lib/api/sse")>()), streamMessage: vi.fn() }));

afterEach(() => vi.restoreAllMocks());

const action = (patch: Partial<ActionView> = {}): ActionView => ({
  id: "a1",
  message_id: "m2",
  kind: "create_scenario",
  summary: "Créer le scénario « Prix -10 » : prix de Sfax -10 %",
  status: "pending",
  payload: {},
  result: null,
  error: null,
  expires_at: "2026-10-03T12:30:00Z",
  decided_at: null,
  ...patch,
});

const message = (patch: Partial<MessageView>): MessageView => ({
  id: "m",
  role: "assistant",
  content: "",
  verification: null,
  tool_trace: null,
  model: "mock",
  prompt_id: "copilot_system@v1",
  created_at: "2026-10-03T12:00:00Z",
  ...patch,
});

describe("verified numbers", () => {
  it("splits the backend's ⟦?…⟧ markers", () => {
    expect(splitVerified("Profit 29 175 TND, gain ⟦?4 000⟧ TND")).toEqual([
      { text: "Profit 29 175 TND, gain ", unverified: false },
      { text: "4 000", unverified: true },
      { text: " TND", unverified: false },
    ]);
  });

  it("highlights unverified numbers instead of hiding them", () => {
    const { container } = render(<VerifiedText text="Profit ⟦?123⟧ TND" />);
    const mark = container.querySelector("mark[data-unverified]");
    expect(mark).toHaveTextContent("123");
    expect(mark).toHaveAttribute("title", expect.stringMatching(/non vérifié/));
  });

  it("badges say verified / how many are not", () => {
    const { rerender } = render(<VerificationBadge verification={{ status: "verified", unknown_refs: [], unverified_numbers: [], checked_numbers: 3, regenerated: false }} />);
    expect(screen.getByText("Chiffres vérifiés")).toBeInTheDocument();
    rerender(<VerificationBadge verification={{ status: "unverified", unknown_refs: ["r1.x"], unverified_numbers: ["123"], checked_numbers: 3, regenerated: true }} />);
    expect(screen.getByText("2 chiffres non vérifiés")).toBeInTheDocument();
  });
});

describe("<ActionCard> — nothing changes without confirmation", () => {
  it("confirms a pending proposal and links to the result", async () => {
    const confirmed = action({ status: "executed", result: { scenario_id: "s1" } });
    const spy = vi.spyOn(api, "confirmAction").mockResolvedValue(confirmed);
    const onChange = vi.fn();
    render(<ActionCard action={action()} onChange={onChange} />);
    expect(screen.getByText(/Rien n'est modifié sans votre confirmation/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Confirmer" }));
    expect(spy).toHaveBeenCalledWith("a1");
    expect(onChange).toHaveBeenCalledWith(confirmed);
  });

  it("rejects, and shows no buttons once decided", async () => {
    vi.spyOn(api, "rejectAction").mockResolvedValue(action({ status: "rejected" }));
    const onChange = vi.fn();
    const { rerender } = render(<ActionCard action={action()} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Refuser" }));
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ status: "rejected" }));
    rerender(<ActionCard action={action({ status: "expired" })} onChange={onChange} />);
    expect(screen.queryByRole("button", { name: "Confirmer" })).not.toBeInTheDocument();
    expect(screen.getByText("Expirée")).toBeInTheDocument();
  });

  it("result links per kind", () => {
    expect(resultHref(action({ status: "executed", result: { scenario_id: "s1" } }))?.href).toBe("/scenarios/s1");
    expect(resultHref(action({ kind: "run_optimization", status: "executed", result: { run_id: "r1" } }))?.href).toBe("/runs/r1/summary");
    expect(resultHref(action({ kind: "generate_report", status: "executed", result: { report_id: "p1" } }))?.href).toBe("/reports/p1");
    expect(resultHref(action())).toBeNull();
  });
});

describe("page context", () => {
  it("reads the entity on screen from the URL", () => {
    expect(contextFromLocation("/runs/abc/explain", new URLSearchParams())).toMatchObject({ run_id: "abc", page: "/runs/abc/explain" });
    expect(contextFromLocation("/scenarios/s1", new URLSearchParams())).toMatchObject({ scenario_id: "s1", run_id: null });
    expect(contextFromLocation("/compare", new URLSearchParams("baseline=r1&runs=r2,r3"))).toMatchObject({ run_id: "r1", compare_run_ids: ["r2", "r3"] });
    expect(contextFromLocation("/optimize", new URLSearchParams("dataset=d1"))).toMatchObject({ dataset_id: "d1" });
  });
});

describe("SSE parsing", () => {
  it("parses complete events and keeps the unfinished remainder", () => {
    const chunk = 'event: tool_call\ndata: {"name":"get_run","arguments":"{}"}\n\nevent: answer\ndata: {"mess';
    const { events, rest } = parseSse(chunk);
    expect(events).toEqual([{ event: "tool_call", data: { name: "get_run", arguments: "{}" } }]);
    expect(rest).toBe('event: answer\ndata: {"mess');
  });
});

describe("<CopilotChat>", () => {
  it("streams tool activity, then shows the verified answer and the proposal", async () => {
    vi.spyOn(api, "createConversation").mockResolvedValue({ id: "c1", title: "", created_at: "", updated_at: "", context: null, messages: [], actions: [] });
    vi.mocked(streamMessage).mockImplementation(async (_id, content, _ctx, onEvent: (e: CopilotEvent) => void) => {
      onEvent({ event: "user_message", data: message({ id: "m1", role: "user", content }) });
      onEvent({ event: "tool_call", data: { name: "create_scenario", arguments: "{}" } });
      onEvent({ event: "tool_result", data: { name: "create_scenario", ok: true, summary: "scénario proposé" } });
      onEvent({
        event: "answer",
        data: {
          message: message({
            id: "m2",
            content: "Le profit actuel est 29 175 TND ; avec ⟦?31 000⟧ TND…",
            verification: { status: "unverified", unknown_refs: [], unverified_numbers: ["31 000"], checked_numbers: 2, regenerated: true },
          }),
          actions: [action()],
        },
      });
    });
    const onConversation = vi.fn();
    render(<CopilotChat conversationId={null} context={{ page: "/runs/r1", run_id: "r1", compare_run_ids: [] }} onConversation={onConversation} />);
    await userEvent.type(screen.getByRole("textbox", { name: "Message au Copilot" }), "Crée un scénario prix -10 %{Enter}");

    const log = screen.getByRole("log", { name: "Messages du Copilot" });
    await within(log).findByText(/Le profit actuel est/);
    expect(onConversation).toHaveBeenCalledWith("c1");
    expect(vi.mocked(streamMessage)).toHaveBeenCalledWith("c1", "Crée un scénario prix -10 %", expect.objectContaining({ run_id: "r1" }), expect.any(Function));
    expect(log.querySelector("mark[data-unverified]")).toHaveTextContent("31 000");
    expect(within(log).getByText("1 chiffre non vérifié")).toBeInTheDocument();
    expect(within(log).getByRole("article", { name: "Proposition : Nouveau scénario" })).toBeInTheDocument();
  });

  it("shows the error event without crashing", async () => {
    vi.mocked(streamMessage).mockImplementation(async (_id, _c, _ctx, onEvent: (e: CopilotEvent) => void) => {
      onEvent({ event: "error", data: { code: "LLM_UPSTREAM_ERROR", message: "Le service IA ne répond pas." } });
    });
    vi.spyOn(api, "conversation").mockResolvedValue({ id: "c1", title: "", created_at: "", updated_at: "", context: null, messages: [], actions: [] });
    render(<CopilotChat conversationId="c1" context={{ compare_run_ids: [] }} onConversation={vi.fn()} />);
    await userEvent.type(screen.getByRole("textbox", { name: "Message au Copilot" }), "Bonjour{Enter}");
    expect(await screen.findByText("Le service IA ne répond pas.")).toBeInTheDocument();
  });
});

describe("<CopilotDrawer>", () => {
  it("says 'IA désactivée' without a key, and the app shell keeps working", async () => {
    vi.spyOn(api, "meta").mockResolvedValue({ ...META, llm: { ...META.llm, configured: false } });
    render(<CopilotDrawer />);
    await userEvent.click(screen.getByRole("button", { name: "Copilot" }));
    const drawer = screen.getByRole("dialog", { name: "Copilot" });
    await waitFor(() => expect(within(drawer).getByText("IA désactivée")).toBeInTheDocument());
    expect(within(drawer).queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("opens a chat when the AI is configured", async () => {
    vi.spyOn(api, "meta").mockResolvedValue({ ...META, llm: { ...META.llm, configured: true } });
    render(<CopilotDrawer />);
    await userEvent.click(screen.getByRole("button", { name: "Copilot" }));
    expect(await screen.findByRole("textbox", { name: "Message au Copilot" })).toBeInTheDocument();
  });
});
