import { defineConfig, devices } from "@playwright/test";
import os from "node:os";
import path from "node:path";

// E2E runs against the real backend (FastAPI + CBC) and the Next dev server. Running servers on
// these ports are reused; otherwise they are started, the backend on a throwaway SQLite file.
const API_PORT = 8000;
const WEB_PORT = 5173;
const python = process.platform === "win32" ? path.join(".venv", "Scripts", "python") : path.join(".venv", "bin", "python");
const copilotScript = path.resolve("e2e", "fixtures", "copilot-script.json");
const e2eDb = path.join(os.tmpdir(), `h2v-e2e-${Date.now()}.db`).split(path.sep).join("/");

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `${python} -m uvicorn app.main:app --port ${API_PORT}`,
      cwd: "../backend",
      url: `http://localhost:${API_PORT}/api/v2/health`,
      reuseExistingServer: true,
      timeout: 120_000,
      // The mock LLM replays e2e/fixtures/copilot-script.json (E2E n°4 Copilot).
      env: { DATABASE_URL: `sqlite:///${e2eDb}`, LLM_PROVIDER: "mock", LLM_MOCK_SCRIPT: copilotScript },
    },
    {
      command: `npm run dev`,
      url: `http://localhost:${WEB_PORT}`,
      reuseExistingServer: true,
      timeout: 180_000,
      env: { NEXT_PUBLIC_API_URL: `http://localhost:${API_PORT}` },
    },
  ],
});
