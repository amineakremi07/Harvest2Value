// Minimal fetch wrapper for /api/v2: JSON in/out, error envelope -> ApiError.
import type { ErrorDetail } from "./types";

export const API_ORIGIN = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const API_V2 = `${API_ORIGIN}/api/v2`;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function isErrorEnvelope(body: unknown): body is { error: ErrorDetail } {
  if (typeof body !== "object" || body === null || !("error" in body)) return false;
  const error = (body as { error: unknown }).error;
  return typeof error === "object" && error !== null && "code" in error && "message" in error;
}

type Query = Record<string, string | number | boolean | null | undefined>;

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Query;
  signal?: AbortSignal;
}

function buildUrl(path: string, query?: Query): string {
  const url = new URL(`${API_V2}${path}`);
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null) url.searchParams.set(key, String(value));
  }
  return url.toString();
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, query, signal } = options;
  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      signal,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError(0, "NETWORK_ERROR", `API unreachable (${API_ORIGIN}). Is the backend running?`);
  }

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  let parsed: unknown = undefined;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = text;
    }
  }

  if (!response.ok) {
    if (isErrorEnvelope(parsed)) {
      throw new ApiError(response.status, parsed.error.code, parsed.error.message, parsed.error.details ?? {});
    }
    throw new ApiError(response.status, "HTTP_ERROR", `Request failed (${response.status})`);
  }
  return parsed as T;
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "Unexpected error";
}
