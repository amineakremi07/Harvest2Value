"use client";

import { useCallback, useSyncExternalStore } from "react";
import { applyChoice, readChoice, THEME_EVENT, type Theme, type ThemeChoice } from "./theme";

function subscribe(onChange: () => void): () => void {
  const media = window.matchMedia?.("(prefers-color-scheme: light)");
  const onSystem = () => {
    if (readChoice() === "system") applyChoice("system");
    onChange();
  };
  window.addEventListener(THEME_EVENT, onChange);
  window.addEventListener("storage", onChange);
  media?.addEventListener?.("change", onSystem);
  return () => {
    window.removeEventListener(THEME_EVENT, onChange);
    window.removeEventListener("storage", onChange);
    media?.removeEventListener?.("change", onSystem);
  };
}

export function useTheme(): { choice: ThemeChoice; theme: Theme; setChoice: (choice: ThemeChoice) => void } {
  const choice = useSyncExternalStore<ThemeChoice>(subscribe, readChoice, () => "system");
  const theme = useSyncExternalStore<Theme>(subscribe, () => (document.documentElement.dataset.theme === "light" ? "light" : "dark"), () => "dark");
  const setChoice = useCallback((next: ThemeChoice) => applyChoice(next), []);
  return { choice, theme, setChoice };
}
