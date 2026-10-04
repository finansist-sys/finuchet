import { useEffect, useState } from "react";
import { Icon } from "../components/Icon";
import { TxRow } from "../components/TxRow";
import { Skeleton } from "../components/ui";
import { api, type Home as HomeData, type Tx } from "../lib/api";
import { monthName, weekdayShort } from "../lib/i18n";
import { formatMoney, currencyInfo } from "../lib/money";
import { useStore } from "../store";

const TIP_KEY = "finuchet.tip.chat";

function readTip(): boolean {
  try {
    return localStorage.getItem(TIP_KEY) !== "1";
  } catch {
    return true;
  }
}

export function openTx(tx: Tx, push: ReturnType<typeof useStore>["push"]) {
  if (tx.kind === "expense" || tx.kind === "income") push({ name: "add", kind: tx.kind, tx });
  else push({ name: "history" });
}

export function Home() {
  const { t, lang, accounts, push, dataVersion, bump, showError, reloadAccounts } = useStore();
  const [data, setData] = useState<HomeData | null>(null);
  const [tip, setTip] = useState(readTip);

  useEffect(() => {
    Promise.all([api.get<HomeData>("/api/stats/home"), reloadAccounts()])
      .then(([home]) => setData(home))
      .catch(showError);
  }, [dataVersion, showError, reloadAccounts]);

  // Entries made in the bot chat appear as soon as the user comes back.
  useEffect(() => {
    const onVisible = () => document.visibilityState === "visible" && bump();
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [bump]);

  if (!data) {
    return (
      <main className="screen">
        <Skeleton height={140} />
        <Skeleton height={120} />
        <Skeleton height={130} />
      </main>
    );
  }

  const cur = data.currency;
  const sym = currencyInfo(cur).symbol;
  const active = accounts.filter((a) => !a.archived && a.currency === cur);
  const cardSum = active.filter((a) => a.type === "card").reduce((s, a) => s + a.balance, 0);
  const cashSum = active.filter((a) => a.type === "cash").reduce((s, a) => s + a.balance, 0);
  const others = Object.entries(data.balances).filter(([c]) => c !== cur);
  const month = new Date(data.month.start + "T00:00:00").getMonth();
  const spentShare = data.month.income > 0 ? Math.min(100, (data.month.expense / data.month.income) * 100) : 0;
  const weekMax = Math.max(...data.week.days, 1);
  const weekTotal = data.week.days.reduce((s, v) => s + v, 0);

  function closeTip() {
    setTip(false);
    try {
      localStorage.setItem(TIP_KEY, "1");
    } catch {
      /* storage may be unavailable; the tip just shows again next time */
    }
  }

  return (
    <main className="screen">
      <div className="topbar">
        <button type="button" className="icon-btn" aria-label={t.analytics} onClick={() => push({ name: "analytics" })}>
          <Icon name="chart" size={22} />
        </button>
        <button type="button" className="icon-btn" aria-label={t.settings} onClick={() => push({ name: "settings" })}>
          <Icon name="gear" size={22} />
        </button>
      </div>

      <button type="button" className="hero" onClick={() => push({ name: "accounts" })} aria-label={t.accounts}>
        <span className="hint">{t.total}</span>
        <span className="hero-amount num">
          <b>{formatMoney(data.balances[cur] ?? 0, cur, { whole: true, symbol: false })}</b>
          <span>{sym}</span>
        </span>
        <span className="hero-split hint num">
          <span>
            {t.card} <strong>{formatMoney(cardSum, cur, { whole: true, symbol: false })}</strong>
          </span>
          <span>
            {t.cash} <strong>{formatMoney(cashSum, cur, { whole: true, symbol: false })}</strong>
          </span>
        </span>
        {others.length > 0 && (
          <span className="hint small num">
            {t.andMore} {others.map(([c, v]) => formatMoney(v, c, { whole: true })).join(", ")}
          </span>
        )}
      </button>

      <section className="card">
        <div className="between">
          <span className="hint">
            {t.spentIn} {monthName(lang, month, true)}
          </span>
          {data.month.income > 0 && (
            <span className="hint num">
              {t.of} {formatMoney(data.month.income, cur, { whole: true, symbol: false })}
            </span>
          )}
        </div>
        <div className="big-num num">{formatMoney(data.month.expense, cur)}</div>
        {data.month.income > 0 && (
          <div className="progress" role="img" aria-label={`${Math.round(spentShare)}%`}>
            <div style={{ width: `${spentShare}%` }} />
          </div>
        )}
      </section>

      <section className="card">
        <div className="between">
          <span className="hint">{t.weekSpent}</span>
          <span className="num" style={{ fontWeight: 500 }}>
            {formatMoney(weekTotal, cur)}
          </span>
        </div>
        <div
          className="week-bars"
          role="img"
          aria-label={data.week.days.map((v, i) => `${weekdayShort(lang, i)} ${formatMoney(v, cur)}`).join(", ")}
        >
          {data.week.days.map((v, i) => (
            <div
              key={i}
              className={i === data.week.today_index ? "today" : ""}
              style={{ height: `${Math.max(4, (v / weekMax) * 56)}px`, opacity: i > data.week.today_index ? 0.35 : 1 }}
            />
          ))}
        </div>
        <div className="week-labels">
          {data.week.days.map((_, i) => (
            <span key={i} className={i === data.week.today_index ? "today" : ""}>
              {weekdayShort(lang, i)}
            </span>
          ))}
        </div>
      </section>

      {tip && (
        <div className="tip">
          <Icon name="list" />
          <span className="grow">{t.chatHint}</span>
          <button type="button" className="link-btn" onClick={closeTip}>
            {t.gotIt}
          </button>
        </div>
      )}

      <section className="list">
        <div className="between" style={{ padding: "0 4px" }}>
          <h2 className="title">{t.recent}</h2>
          <button type="button" className="link-btn" onClick={() => push({ name: "history" })}>
            {t.all}
          </button>
        </div>
        {data.recent.length === 0 ? (
          <div className="empty">
            <b>{t.emptyTitle}</b>
            <span className="hint">{t.emptyText}</span>
          </div>
        ) : (
          data.recent.map((tx) => <TxRow key={tx.id} tx={tx} onOpen={(x) => openTx(x, push)} />)
        )}
      </section>

      <div className="btn-row sticky-actions">
        <button type="button" className="btn btn-primary" onClick={() => push({ name: "add", kind: "expense" })}>
          {t.expense}
        </button>
        <button type="button" className="btn btn-tonal" onClick={() => push({ name: "add", kind: "income" })}>
          {t.income}
        </button>
      </div>
    </main>
  );
}
