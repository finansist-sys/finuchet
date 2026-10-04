// Money formatting and numpad input. Amounts are integers in minor units.

export type CurrencyInfo = { symbol: string; exponent: number };

const FALLBACK: CurrencyInfo = { symbol: "", exponent: 2 };
const registry = new Map<string, CurrencyInfo>();

export function registerCurrencies(list: { code: string; symbol: string; exponent: number }[]): void {
  for (const c of list) registry.set(c.code, { symbol: c.symbol, exponent: c.exponent });
}

/** "₽ RUB", or just "AED" when the currency has no separate symbol. */
export function currencyLabel(code: string): string {
  const { symbol } = currencyInfo(code);
  return symbol && symbol !== code ? `${symbol} ${code}` : code;
}

export function currencyInfo(code: string): CurrencyInfo {
  return registry.get(code) ?? { ...FALLBACK, symbol: code };
}

const NBSP = " ";
const THIN = " ";

function groupThousands(n: bigint): string {
  return n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, THIN);
}

/** 14832050 RUB -> "148 320,50 ₽". `whole` drops the fraction (for big hero numbers). */
export function formatMoney(
  minor: number,
  code: string,
  opts: { signed?: boolean; whole?: boolean; symbol?: boolean } = {},
): string {
  const { exponent, symbol } = currencyInfo(code);
  const neg = minor < 0;
  const abs = BigInt(Math.abs(Math.round(minor)));
  const base = 10n ** BigInt(exponent);
  const int = exponent ? abs / base : abs;
  const frac = exponent ? abs % base : 0n;
  let out = groupThousands(int);
  if (!opts.whole && exponent && frac !== 0n) out += "," + frac.toString().padStart(exponent, "0");
  const sign = neg ? "−" : opts.signed && minor > 0 ? "+" : "";
  return sign + out + (opts.symbol === false ? "" : NBSP + symbol);
}

/** Parse the numpad string ("1250,5") to minor units. Returns 0 for empty/invalid input. */
export function parseInput(input: string, code: string): number {
  const { exponent } = currencyInfo(code);
  const m = /^(\d{0,13})(?:,(\d{0,3}))?$/.exec(input);
  if (!m) return 0;
  const int = m[1] || "0";
  const frac = (m[2] ?? "").slice(0, exponent).padEnd(exponent, "0");
  const value = BigInt(int) * 10n ** BigInt(exponent) + (exponent ? BigInt(frac || "0") : 0n);
  return Number(value);
}

/** Minor units -> numpad string, e.g. 30050 RUB -> "300,5". */
export function toInput(minor: number, code: string): string {
  const { exponent } = currencyInfo(code);
  if (!exponent) return String(Math.abs(minor));
  const base = 10 ** exponent;
  const int = Math.floor(Math.abs(minor) / base);
  const frac = Math.abs(minor) % base;
  return frac ? `${int},${String(frac).padStart(exponent, "0").replace(/0+$/, "")}` : String(int);
}

/** Apply a numpad key to the current input string, enforcing currency precision and length. */
export function pressKey(current: string, key: string, code: string): string {
  const { exponent } = currencyInfo(code);
  if (key === "⌫") return current.slice(0, -1);
  if (key === ",") {
    if (!exponent || current.includes(",")) return current;
    return (current || "0") + ",";
  }
  if (!/^\d$/.test(key)) return current;
  const [int, frac] = current.split(",");
  if (frac !== undefined) return frac.length >= exponent ? current : current + key;
  if (int === "0") return key;
  if (int.length >= 12) return current;
  return current + key;
}
