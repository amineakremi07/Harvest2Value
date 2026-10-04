"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/lib/theme/useTheme";

/** One-click switch between the light and dark themes (the settings page also offers "system"). */
export function ThemeToggle() {
  const { theme, setChoice } = useTheme();
  const next = theme === "dark" ? "light" : "dark";
  return (
    <button
      type="button"
      onClick={() => setChoice(next)}
      aria-label={next === "light" ? "Passer au thème clair" : "Passer au thème sombre"}
      title={next === "light" ? "Thème clair" : "Thème sombre"}
      className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-slate-300 hover:bg-white/5"
    >
      {theme === "dark" ? <Sun className="h-4 w-4" aria-hidden="true" /> : <Moon className="h-4 w-4" aria-hidden="true" />}
    </button>
  );
}
