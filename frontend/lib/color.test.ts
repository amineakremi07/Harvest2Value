import { describe, expect, it } from "vitest";
import { cellStyle } from "@/features/optimization/AllocationMatrix";
import { contrast } from "./color";

const rgb = (css: string) => css.match(/\d+/g)!.slice(0, 3).map(Number) as [number, number, number];

describe("heatmap text stays WCAG AA (4.5:1) on every shade, in both themes", () => {
  it.each(["dark", "light"] as const)("%s theme", (theme) => {
    for (let kg = 1; kg <= 100; kg++) {
      const style = cellStyle(kg, 100, theme)!;
      expect(contrast(rgb(String(style.color)), rgb(String(style.backgroundColor)))).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("contrast() matches the WCAG reference values", () => {
    expect(contrast([0, 0, 0], [255, 255, 255])).toBeCloseTo(21, 5);
    expect(contrast([118, 118, 118], [255, 255, 255])).toBeCloseTo(4.54, 2);
  });
});
