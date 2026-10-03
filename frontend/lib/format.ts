const kgFormat = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
const numFormat = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 });
const pctFormat = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });
const dateFormat = new Intl.DateTimeFormat("fr-FR", { dateStyle: "short", timeStyle: "short" });

export const DEFAULT_CURRENCY = "TND";

export function fmtKg(value: number | null | undefined): string {
  return value == null ? "—" : `${kgFormat.format(value + 0)} kg`;
}

export function fmtNum(value: number | null | undefined): string {
  // `+ 0` turns -0 (e.g. a rounded right-hand side) into 0.
  return value == null ? "—" : numFormat.format(value + 0);
}

export function fmtMoney(value: number | null | undefined, currency: string = DEFAULT_CURRENCY): string {
  return value == null ? "—" : `${kgFormat.format(value + 0)} ${currency}`;
}

export function fmtPct(value: number | null | undefined): string {
  return value == null ? "—" : `${pctFormat.format(value)} %`;
}

export function fmtSigned(value: number | null | undefined, suffix = ""): string {
  if (value == null) return "—";
  const sign = value > 0 ? "+" : value < 0 ? "−" : "±";
  return `${sign}${numFormat.format(Math.abs(value))}${suffix}`;
}

export function fmtDate(iso: string | null | undefined): string {
  return iso ? dateFormat.format(new Date(iso)) : "—";
}

export function fmtUnit(value: number | null | undefined, unit: string, currency: string = DEFAULT_CURRENCY): string {
  switch (unit) {
    case "currency":
      return fmtMoney(value, currency);
    case "currency/kg":
      return value == null ? "—" : `${numFormat.format(value)} ${currency}/kg`;
    case "kg":
      return fmtKg(value);
    case "%":
      return fmtPct(value);
    default:
      return value == null ? "—" : `${fmtNum(value)} ${unit}`;
  }
}

export function shortId(id: string): string {
  return id.length > 8 ? id.slice(0, 8) : id;
}
