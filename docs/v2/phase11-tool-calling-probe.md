# Phase 11 prerequisite — real tool-calling test

Date: 2026-10-02 · Script: `backend/scripts/probe_tool_calling.py` (synthetic data only, nothing written).

## Setup

- Provider tested: **Groq** (OpenAI-compatible `/chat/completions`, `tools` + `tool_choice: auto`), key from `GROQ_API_KEY`.
- **NVIDIA NIM not tested**: no NIM key is configured on this machine. The NIM provider uses the
  same OpenAI-compatible client; re-run the probe with `LLM_PROVIDER=nvidia_nim LLM_API_KEY=...`.
- Two tools (`get_run`, `get_buyer_analysis` with an `enum` argument), a system prompt requiring
  `{{ref:...}}` references instead of numbers, tool results fed back, up to 3 tool rounds.
- Cases: single tool (FR), no tool needed (FR), enum argument (FR), two tools (EN).

## Results

| Model | Runs | Correct tools | Valid args (JSON, required, enum) | Final answer | Raw numbers in answer |
|---|---|---|---|---|---|
| `openai/gpt-oss-120b` (default) | 12 (4 cases × 3) | 11/11 | 11/11 | 11/11 | 0 |
| `openai/gpt-oss-20b` | 4 | 4/4 | 4/4 | 4/4 | 0 |
| `llama-3.3-70b-versatile` | — | — | — | HTTP 404: not available to this account | — |

The single failure (`gpt-oss-120b`, 12th call) was **HTTP 429 — tokens-per-minute rate limit**, not a
tool-calling problem. Latency 1.2–3.5 s per case (1–2 tool rounds).

**Verdict: tool calling works cleanly → phase 11 proceeds** (no alternative needed).

## Findings that shaped the design

1. **Invented reference paths.** The model cites numbers with refs but sometimes invents the path
   (`{{ref:r2.buyers.0.net_revenue}}`, `{{ref:r2.buyer_analysis.sold_kg}}`). → Every tool result
   carries an explicit `refs` map (exact path → value, unit); the prompt says to use only those keys;
   the `NumericVerifier` rejects unknown refs and triggers at most one regeneration.
2. **Invented units.** One answer appended "€" to a TND amount. → Rendered refs include the unit and
   currency (`29 175 TND`); the prompt forbids writing units after a ref.
3. **Rate limits.** Groq's on-demand tier hits TPM limits during bursts. → The copilot retries once on
   429 with a short backoff and otherwise answers with a clear "AI temporarily unavailable" error; the
   rest of the app never depends on the LLM.
