"use client";

import { ThemeProvider as NextThemes } from "next-themes";

/** Light / Dark / System — `<html class="dark">`; standart: tizim sozlamasi. */
export default function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemes attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      {children}
    </NextThemes>
  );
}
