import { beforeAll, describe, expect, it } from "vitest";
import { formatMoney, parseInput, pressKey, registerCurrencies, toInput } from "./money";

beforeAll(() =>
  registerCurrencies([
    { code: "RUB", symbol: "₽", exponent: 2 },
    { code: "USD", symbol: "$", exponent: 2 },
    { code: "JPY", symbol: "¥", exponent: 0 },
    { code: "KWD", symbol: "KD", exponent: 3 },
  ]),
);

describe("formatMoney", () => {
  it("groups thousands and shows kopecks", () => {
    expect(formatMoney(14832050, "RUB")).toBe("148 320,50 ₽");
  });
  it("hides zero fraction and supports signs", () => {
    expect(formatMoney(30000, "RUB")).toBe("300 ₽");
    expect(formatMoney(-35000, "RUB")).toBe("−350 ₽");
    expect(formatMoney(8500000, "RUB", { signed: true })).toBe("+85 000 ₽");
  });
  it("respects currency exponents", () => {
    expect(formatMoney(1500, "JPY")).toBe("1 500 ¥");
    expect(formatMoney(1235, "KWD")).toBe("1,235 KD");
  });
  it("can drop fraction and symbol", () => {
    expect(formatMoney(14832050, "RUB", { whole: true, symbol: false })).toBe("148 320");
  });
});

describe("numpad input", () => {
  it("parses input to minor units", () => {
    expect(parseInput("300", "RUB")).toBe(30000);
    expect(parseInput("300,5", "RUB")).toBe(30050);
    expect(parseInput("1500", "JPY")).toBe(1500);
    expect(parseInput("", "RUB")).toBe(0);
    expect(parseInput("abc", "RUB")).toBe(0);
  });
  it("round-trips", () => {
    expect(toInput(30050, "RUB")).toBe("300,5");
    expect(toInput(30000, "RUB")).toBe("300");
    expect(parseInput(toInput(123456, "RUB"), "RUB")).toBe(123456);
  });
  it("applies keys with precision limits", () => {
    let s = "";
    for (const k of ["0", "3", "5", "0", ",", "5", "0", "9"]) s = pressKey(s, k, "RUB");
    expect(s).toBe("350,50");
    expect(pressKey("12", ",", "JPY")).toBe("12");
    expect(pressKey("1,5", ",", "RUB")).toBe("1,5");
    expect(pressKey("12", "⌫", "RUB")).toBe("1");
    expect(pressKey("123456789012", "3", "RUB")).toBe("123456789012");
  });
});
