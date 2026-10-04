import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api/endpoints";
import { applyChoice, readChoice, resolveTheme, THEME_STORAGE_KEY } from "@/lib/theme/theme";
import { OLIVES_RUN } from "@/test/fixtures";
import { CommandPalette, openCommandPalette } from "./CommandPalette";
import { ThemeToggle } from "./ThemeToggle";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), back: vi.fn(), refresh: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

beforeEach(() => {
  window.localStorage.clear();
  document.documentElement.dataset.theme = "dark";
  push.mockReset();
});
afterEach(() => vi.restoreAllMocks());

describe("theme", () => {
  it("stores an explicit choice and applies it to <html>", () => {
    applyChoice("light");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    applyChoice("system");
    expect(readChoice()).toBe("system");
    expect(document.documentElement.dataset.theme).toBe(resolveTheme("system"));
  });

  it("the toggle switches theme and says what it will do", async () => {
    render(<ThemeToggle />);
    await userEvent.click(screen.getByRole("button", { name: "Passer au thème clair" }));
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(screen.getByRole("button", { name: "Passer au thème sombre" })).toBeInTheDocument();
  });
});

describe("<CommandPalette>", () => {
  function mockLists() {
    vi.spyOn(api, "runs").mockResolvedValue({ items: [{ ...OLIVES_RUN, label: "Référence olives" }], total: 1, page: 1, page_size: 15 });
    vi.spyOn(api, "datasets").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 15 });
    vi.spyOn(api, "scenarios").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 15 });
    vi.spyOn(api, "reports").mockResolvedValue({ items: [], total: 0, page: 1, page_size: 100 });
  }

  it("opens with Ctrl+K, filters, and navigates to a page", async () => {
    mockLists();
    render(<CommandPalette />);
    await userEvent.keyboard("{Control>}k{/Control}");
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByRole("combobox"), "rapports");
    await userEvent.keyboard("{Enter}");
    expect(push).toHaveBeenCalledWith("/reports");
  });

  it("lists recent runs and opens one", async () => {
    mockLists();
    render(<CommandPalette />);
    act(() => openCommandPalette());
    const item = await screen.findByRole("option", { name: /Référence olives/ });
    await userEvent.click(item);
    expect(push).toHaveBeenCalledWith(`/runs/${OLIVES_RUN.id}/summary`);
  });
});
