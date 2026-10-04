import { useEffect, useMemo, useState } from "react";
import { Donut } from "../components/Donut";
import { Icon } from "../components/Icon";
import { Segmented, Skeleton } from "../components/ui";
import { api, type CategoryStats } from "../lib/api";
import { monthName } from "../lib/i18n";
import { currencyInfo, formatMoney } from "../lib/money";
import { slotColor } from "../lib/palette";
import { useStore } from "../store";

type Period = "week" | "month" | "year";
const MAX_SEGMENTS = 5; // the rest folds into "Other"

export function Analytics() {
  const { t, lang, me, scheme, accounts, categories, push, showError, dataVersion } = useStore();
  const base = me?.onboarded ? me.base_currency : "RUB";
  const [period, setPeriod] = useState<Period>("month");
  const [offset, setOffset] = useState(0);
  const [currency, setCurrency] = useState(base);
  const [data, setData] = useState<CategoryStats | null>(null);

  const usedCurrencies = useMemo(() => {
    const set = new Set(accounts.filter((a) => !a.archived).map((a) => a.currency));
    set.add(base);
    return [base, ...[...set].filter((c) => c !== base)];
  }, [accounts, base]);

  useEffect(() => {
    setData(null);
    const q = new URLSearchParams({ period, offset: String(offset), currency });
    api.get<CategoryStats>(`/api/stats/categories?${q}`).then(setData).catch(showError);
  }, [period, offset, currency, showError, dataVersion]);

  const title = useMemo(() => {
    if (!data) return "";
    const start = new Date(data.start + "T00:00:00");
    if (period === "year") return String(start.getFullYear());
    if (period === "month") {
      const name = monthName(lang, start.getMonth());
      return start.getFullYear() === new Date().getFullYear() ? name : `${name} ${start.getFullYear()}`;
    }
    const end = new Date(data.end + "T00:00:00");
    end.setDate(end.getDate() - 1);
    const fmt = (d: Date) => d.toLocaleDateString(lang === "ru" ? "ru-RU" : "en-GB", { day: "numeric", month: "short" });
    return `${fmt(start)} – ${fmt(end)}`;
  }, [data, period, lang]);

  const rows = useMemo(() => {
    if (!data) return [];
    const list = data.categories.map((c) => {
      const cat = categories.find((x) => x.id === c.category_id);
      return {
        id: c.category_id,
        name: cat?.name ?? t.noCategory,
        color: slotColor(cat?.color ?? -1, scheme),
        amount: c.amount,
      };
    });
    if (list.length <= MAX_SEGMENTS) return list;
    const head = list.slice(0, MAX_SEGMENTS - 1);
    const rest = list.slice(MAX_SEGMENTS - 1).reduce((s, x) => s + x.amount, 0);
    return [...head, { id: null, name: t.other, color: slotColor(-1, scheme), amount: rest }];
  }, [data, categories, scheme, t]);

  const total = data?.expense ?? 0;
  const pct = (v: number) => (total ? `${Math.round((v / total) * 100)}%` : "0%");

  return (
    <main className="screen">
      <Segmented
        options={[
          { value: "week", label: t.week },
          { value: "month", label: t.month },
          { value: "year", label: t.year },
        ]}
        value={period}
        onChange={(p) => {
          setPeriod(p);
          setOffset(0);
        }}
      />

      <div className="row" style={{ justifyContent: "center" }}>
        <button type="button" className="icon-btn" aria-label="‹" onClick={() => setOffset((o) => o - 1)}>
          <Icon name="left" />
        </button>
        <h1 className="h1 center" style={{ minWidth: 150 }}>
          {title || "…"}
        </h1>
        <button
          type="button"
          className="icon-btn"
          aria-label="›"
          disabled={offset >= 0}
          style={{ opacity: offset >= 0 ? 0.3 : 1 }}
          onClick={() => setOffset((o) => Math.min(0, o + 1))}
        >
          <Icon name="right" />
        </button>
      </div>

      {usedCurrencies.length > 1 && (
        <div className="chips" style={{ justifyContent: "center" }}>
          {usedCurrencies.map((c) => (
            <button key={c} type="button" className="chip" aria-pressed={c === currency} onClick={() => setCurrency(c)}>
              {currencyInfo(c).symbol}
            </button>
          ))}
        </div>
      )}

      {!data ? (
        <Skeleton height={220} />
      ) : (
        <>
          <Donut
            segments={rows.map((r) => ({ value: r.amount, color: r.color, label: r.name }))}
            ariaLabel={rows.map((r) => `${r.name} ${pct(r.amount)}`).join(", ")}
            center={
              <>
                <span className="num" style={{ fontSize: 26, fontWeight: 600 }}>
                  {formatMoney(total, currency, { whole: true })}
                </span>
                <span className="hint small">{t.spent}</span>
              </>
            }
          />

          {rows.length === 0 ? (
            <p className="hint center">{t.nothingInPeriod}</p>
          ) : (
            <div className="list">
              {rows.map((r) => (
                <button
                  key={r.id ?? r.name}
                  type="button"
                  className="legend-row"
                  style={{ background: "none", border: 0, textAlign: "left" }}
                  onClick={() => r.id && push({ name: "history", categoryId: r.id })}
                >
                  <span className="dot" style={{ background: r.color }} />
                  <span>{r.name}</span>
                  <span className="hint num" style={{ textAlign: "right" }}>
                    {pct(r.amount)}
                  </span>
                  <span className="num" style={{ fontWeight: 500, textAlign: "right" }}>
                    {formatMoney(r.amount, currency)}
                  </span>
                </button>
              ))}
            </div>
          )}

          <section className="card summary">
            <div>
              <span className="hint small">{t.incomes}</span>
              <b className="income num">{formatMoney(data.income, currency, { whole: true, symbol: false })}</b>
            </div>
            <div>
              <span className="hint small">{t.expenses}</span>
              <b className="num">{formatMoney(data.expense, currency, { whole: true, symbol: false })}</b>
            </div>
            <div>
              <span className="hint small">{t.left}</span>
              <b className="num">{formatMoney(data.income - data.expense, currency, { whole: true, symbol: false })}</b>
            </div>
          </section>
        </>
      )}
    </main>
  );
}
