// POST + text/event-stream reader for the copilot (EventSource only supports GET).
import { ApiError, API_V2 } from "./client";
import type { ActionView, MessageView, PageContext } from "./types";

export type CopilotEvent =
  | { event: "user_message"; data: MessageView }
  | { event: "tool_call"; data: { name: string; arguments: string } }
  | { event: "tool_result"; data: { name: string; ok: boolean; summary: string } }
  | { event: "answer"; data: { message: MessageView; actions: ActionView[] } }
  | { event: "error"; data: { code: string; message: string } }
  | { event: "done"; data: Record<string, never> };

/** Splits an SSE buffer into complete events; returns them and the unfinished remainder. */
export function parseSse(buffer: string): { events: CopilotEvent[]; rest: string } {
  const blocks = buffer.replace(/\r\n/g, "\n").split("\n\n");
  const rest = blocks.pop() ?? "";
  const events: CopilotEvent[] = [];
  for (const block of blocks) {
    let name = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) name = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
    }
    if (data.length === 0) continue;
    try {
      events.push({ event: name, data: JSON.parse(data.join("\n")) } as CopilotEvent);
    } catch {
      // A malformed event is skipped; the final `answer` is what matters.
    }
  }
  return { events, rest };
}

export async function streamMessage(
  conversationId: string,
  content: string,
  context: PageContext | undefined,
  onEvent: (event: CopilotEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_V2}/copilot/conversations/${conversationId}/messages?stream=true`, {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ content, context }),
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError(0, "NETWORK_ERROR", "API unreachable. Is the backend running?");
  }
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => undefined);
    const error = (body as { error?: { code: string; message: string } } | undefined)?.error;
    throw new ApiError(response.status, error?.code ?? "HTTP_ERROR", error?.message ?? `Request failed (${response.status})`);
  }
  if (!response.body) throw new ApiError(0, "NO_STREAM", "Streaming is not supported by this browser.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parsed = parseSse(buffer);
    buffer = parsed.rest;
    parsed.events.forEach(onEvent);
  }
  parseSse(buffer + "\n\n").events.forEach(onEvent);
}
