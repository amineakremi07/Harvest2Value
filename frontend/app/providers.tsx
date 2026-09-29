"use client";

import { ThemeProvider } from "next-themes";
import type { ReactNode } from "react";
import { DelegationProvider } from "@/app/context/DelegationProvider";

/**
 * next-themes writes the `.dark` class onto <html> from an inline script, so
 * the correct palette is in place before first paint. `<html>` therefore needs
 * `suppressHydrationWarning` — see layout.tsx.
 */
export default function Providers({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem
      disableTransitionOnChange
    >
      <DelegationProvider>{children}</DelegationProvider>
    </ThemeProvider>
  );
}
