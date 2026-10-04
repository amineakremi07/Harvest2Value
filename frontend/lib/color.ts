// WCAG contrast helpers for colors computed at runtime (heatmaps).
type Rgb = [number, number, number];

function channel(c: number): number {
  const s = c / 255;
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
}

export function luminance([r, g, b]: Rgb): number {
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

export function contrast(a: Rgb, b: Rgb): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/** `color` at `alpha` over an opaque `surface`. */
export function blend(color: Rgb, alpha: number, surface: Rgb): Rgb {
  return color.map((c, i) => Math.round(alpha * c + (1 - alpha) * surface[i])) as Rgb;
}

// Pure black / white: the better of the two is always >= 4.58:1, whatever the background.
export const DARK_TEXT: Rgb = [0, 0, 0];
export const LIGHT_TEXT: Rgb = [255, 255, 255];

/** Whichever of dark / light text reads best on `background`. */
export function readableText(background: Rgb): string {
  const dark = contrast(DARK_TEXT, background);
  const light = contrast(LIGHT_TEXT, background);
  const [r, g, b] = dark >= light ? DARK_TEXT : LIGHT_TEXT;
  return `rgb(${r}, ${g}, ${b})`;
}
