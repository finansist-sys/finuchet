import { useMemo, useState } from "react";
import { Numpad, Sheet } from "../components/ui";
import { api, type Me } from "../lib/api";
import { currencyInfo, formatMoney, parseInput, pressKey } from "../lib/money";
import { haptic } from "../lib/telegram";
import { useStore } from "../store";

const POPULAR = ["RUB", "USD", "EUR", "KZT", "BYN", "UAH", "UZS", "AMD", "GEL", "KGS", "TRY", "AED"];

function AmountView({ input, currency }: { input: string; currency: string }) {
  const value = parseInput(input, currency);
  return (
    <div className="amount-display num" aria-live="polite">
      <b className={input ? "" : "placeholder"}>{input ? formatMoney(value, currency, { symbol: false }) : "0"}</b>
      <span>{currencyInfo(currency).symbol}</span>
    </div>
  );
}

export function Onboarding() {
  const { t, lang, currencies, setMe, reloadAccounts, reloadCategories, resetTo, showError } = useStore();
  const [step, setStep] = useState(0);
  const [currency, setCurrency] = useState(lang === "ru" ? "RUB" : "USD");
  const [query, setQuery] = useState("");
  const [cards, setCards] = useState("");
  const [cash, setCash] = useState("");
  const [extraOpen, setExtraOpen] = useState(false);
  const [extra, setExtra] = useState<{ currency: string; input: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const shown = useMemo(() => {
    const q = query.trim().toUpperCase();
    if (q) return currencies.filter((c) => c.code.includes(q) || c.symbol.toUpperCase().includes(q)).map((c) => c.code);
    return POPULAR.filter((code) => currencies.some((c) => c.code === code));
  }, [query, currencies]);

  async function finish() {
    setBusy(true);
    const accounts = [
      { type: "card", name: t.card, currency, balance: parseInput(cards, currency) },
      { type: "cash", name: t.cash, currency, balance: parseInput(cash, currency) },
    ];
    if (extra && parseInput(extra.input, extra.currency) > 0) {
      accounts.push({
        type: "cash",
        name: `${t.cash} ${currencyInfo(extra.currency).symbol}`,
        currency: extra.currency,
        balance: parseInput(extra.input, extra.currency),
      });
    }
    try {
      const me = await api.post<Me>("/api/onboarding", {
        base_currency: currency,
        tz: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
        accounts,
      });
      await Promise.all([reloadAccounts(), reloadCategories()]);
      setMe(me);
      haptic.success();
      resetTo({ name: "home" });
    } catch (e) {
      showError(e);
      setBusy(false);
    }
  }

  if (step === 0) {
    return (
      <main className="screen">
        <div className="center" style={{ padding: "24px 0 8px" }}>
          <h1 className="h1">{t.welcomeTitle}</h1>
          <p className="hint">{t.welcomeText}</p>
        </div>
        <h2 className="title">{t.yourCurrency}</h2>
        <input
          className="input"
          style={{ background: "var(--card)" }}
          placeholder={t.searchCurrency}
          value={query}
          maxLength={12}
          onChange={(e) => setQuery(e.target.value)}
          aria-label={t.searchCurrency}
        />
        <div className="cat-grid">
          {shown.map((code) => (
            <button
              key={code}
              type="button"
              className="chip"
              aria-pressed={code === currency}
              onClick={() => setCurrency(code)}
            >
              {currencyInfo(code).symbol} {code}
            </button>
          ))}
        </div>
        <button className="btn btn-primary push-bottom" type="button" onClick={() => setStep(1)}>
          {t.next}
        </button>
      </main>
    );
  }

  const isCards = step === 1;
  const input = isCards ? cards : cash;
  const setInput = isCards ? setCards : setCash;
  const others = currencies.filter((c) => c.code !== currency);

  return (
    <main className="screen">
      <p className="hint center">{isCards ? "2 / 3" : "3 / 3"}</p>
      <h1 className="h1 center">{isCards ? t.onCards : t.inCash}</h1>
      <AmountView input={input} currency={currency} />
      {!isCards && (
        <div className="quiet-row">
          <button type="button" className="link-btn" onClick={() => setExtraOpen(true)}>
            {extra && parseInput(extra.input, extra.currency) > 0
              ? `+ ${formatMoney(parseInput(extra.input, extra.currency), extra.currency)}`
              : t.extraCurrency}
          </button>
        </div>
      )}
      <div className="push-bottom" />
      <Numpad
        allowComma={currencyInfo(currency).exponent > 0}
        onKey={(k) => setInput((s) => pressKey(s, k, currency))}
      />
      <div className="btn-row">
        <button type="button" className="btn btn-tonal" onClick={() => (isCards ? setStep(2) : setStep(1))}>
          {isCards ? t.skip : "‹"}
        </button>
        <button type="button" className="btn btn-primary" disabled={busy} onClick={() => (isCards ? setStep(2) : finish())}>
          {isCards ? t.next : t.start}
        </button>
      </div>

      <Sheet open={extraOpen} onClose={() => setExtraOpen(false)} label={t.extraCurrency}>
        <h2 className="title">{t.currency}</h2>
        <div className="chips">
          {others.slice(0, 20).map((c) => (
            <button
              key={c.code}
              type="button"
              className="chip"
              style={{ background: "var(--page)" }}
              aria-pressed={extra?.currency === c.code}
              onClick={() => setExtra({ currency: c.code, input: extra?.input ?? "" })}
            >
              {c.symbol} {c.code}
            </button>
          ))}
        </div>
        {extra && (
          <label className="field">
            <span className="hint">{t.extraAmount}</span>
            <input
              className="input num"
              inputMode="decimal"
              value={extra.input}
              maxLength={16}
              onChange={(e) =>
                setExtra({ ...extra, input: e.target.value.replace(".", ",").replace(/[^\d,]/g, "") })
              }
            />
          </label>
        )}
        <button type="button" className="btn btn-primary" onClick={() => setExtraOpen(false)}>
          {t.done}
        </button>
      </Sheet>
    </main>
  );
}
