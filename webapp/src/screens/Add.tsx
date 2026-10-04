import { useEffect, useMemo, useState } from "react";
import { Numpad, Sheet, CatIcon } from "../components/ui";
import { api, type Category, type Kind, type Tx } from "../lib/api";
import { dayLabel } from "../lib/i18n";
import { currencyInfo, formatMoney, parseInput, pressKey, toInput } from "../lib/money";
import { haptic, setClosingConfirmation, setVerticalSwipes } from "../lib/telegram";
import { useStore } from "../store";

type Frequent = { categoryId: string | null; accountId: string; amount: number; label: string };

function noonOf(date: Date): string {
  const d = new Date(date);
  d.setHours(12, 0, 0, 0);
  return d.toISOString();
}

function localDateInput(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export function Add({ kind, tx }: { kind: Kind; tx?: Tx }) {
  const { t, lang, me, accounts, categories, back, bump, showToast, showError } = useStore();
  const active = accounts.filter((a) => !a.archived || a.id === tx?.account_id);
  const defaultAccount =
    active.find((a) => a.id === tx?.account_id) ??
    active.find((a) => me?.onboarded && a.id === me.default_account_id) ??
    active[0];

  const [accountId, setAccountId] = useState(defaultAccount?.id ?? "");
  const account = active.find((a) => a.id === accountId) ?? defaultAccount;
  const cur = account?.currency ?? "RUB";
  const [input, setInput] = useState(tx ? toInput(tx.amount, cur) : "");
  const [categoryId, setCategoryId] = useState<string | null>(tx?.category_id ?? null);
  const [note, setNote] = useState(tx?.note ?? "");
  const [date, setDate] = useState<Date>(tx ? new Date(tx.occurred_at) : new Date());
  const [dateTouched, setDateTouched] = useState(false);
  const [sheet, setSheet] = useState<"account" | "date" | "note" | "cats" | null>(null);
  const [frequent, setFrequent] = useState<Frequent[]>([]);
  const [busy, setBusy] = useState(false);

  const amount = parseInput(input, cur);
  const cats = useMemo(() => categories.filter((c) => c.kind === kind && !c.archived), [categories, kind]);
  const gridCats = cats.length > 8 ? cats.slice(0, 7) : cats;
  const selectedOutsideGrid = categoryId && !gridCats.some((c) => c.id === categoryId);

  useEffect(() => {
    setVerticalSwipes(false);
    return () => {
      setVerticalSwipes(true);
      setClosingConfirmation(false);
    };
  }, []);
  useEffect(() => setClosingConfirmation(amount > 0), [amount]);

  // "Frequent": repeated (category, amount, account) combos from recent history, for one-tap entry.
  useEffect(() => {
    if (tx) return;
    api
      .get<{ items: Tx[] }>(`/api/transactions?limit=100&kind=${kind}`)
      .then(({ items }) => {
        const counts = new Map<string, { n: number; tx: Tx }>();
        for (const it of items) {
          const key = `${it.category_id}|${it.amount}|${it.account_id}`;
          const prev = counts.get(key);
          counts.set(key, { n: (prev?.n ?? 0) + 1, tx: prev?.tx ?? it });
        }
        const top = [...counts.values()]
          .filter((v) => v.n >= 2 && accounts.some((a) => a.id === v.tx.account_id && !a.archived))
          .sort((a, b) => b.n - a.n)
          .slice(0, 3);
        setFrequent(
          top.map(({ tx: it }) => {
            const c = categories.find((x) => x.id === it.category_id);
            const word = it.note?.split(" ")[0];
            const name = word ? word[0].toUpperCase() + word.slice(1) : (c?.name ?? "");
            const acc = accounts.find((a) => a.id === it.account_id);
            return {
              categoryId: it.category_id,
              accountId: it.account_id,
              amount: it.amount,
              label: `${name} ${formatMoney(it.amount, acc?.currency ?? cur, { symbol: false })}`.trim(),
            };
          }),
        );
      })
      .catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, tx]);

  async function save(override?: Frequent) {
    if (busy) return;
    const body = {
      kind,
      account_id: override?.accountId ?? accountId,
      amount: override?.amount ?? amount,
      category_id: override ? override.categoryId : categoryId,
      note: override ? null : note.trim() || null,
      occurred_at: override ? undefined : dateTouched || tx ? date.toISOString() : undefined,
    };
    setBusy(true);
    try {
      if (tx) {
        await api.patch(`/api/transactions/${tx.id}`, body);
        showToast(t.saved);
      } else {
        const res = await api.post<{ transaction: Tx }>("/api/transactions", body);
        showToast(t.saved, {
          label: t.undo,
          run: () => {
            api
              .del(`/api/transactions/${res.transaction.id}`)
              .then(() => {
                bump();
                showToast(t.deleted);
              })
              .catch(showError);
          },
        });
      }
      haptic.success();
      setClosingConfirmation(false);
      bump();
      back();
    } catch (e) {
      showError(e);
      setBusy(false);
    }
  }

  async function remove() {
    if (!tx || busy) return;
    setBusy(true);
    try {
      await api.del(`/api/transactions/${tx.id}`);
      haptic.success();
      showToast(t.deleted);
      bump();
      back();
    } catch (e) {
      showError(e);
      setBusy(false);
    }
  }

  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);

  function tile(c: Category) {
    return (
      <button
        key={c.id}
        type="button"
        className="cat-tile"
        aria-pressed={c.id === categoryId}
        onClick={() => {
          haptic.tap();
          setCategoryId(c.id);
          setSheet(null);
        }}
      >
        <CatIcon category={c} selected={c.id === categoryId} size={46} />
        <span>{c.name}</span>
      </button>
    );
  }

  return (
    <main className="screen" style={{ gap: 20 }}>
      <div className="center hint">{kind === "expense" ? t.expense : t.income}</div>
      <div className="amount-display num" aria-live="polite">
        <b className={input ? "" : "placeholder"}>{input ? formatMoney(amount, cur, { symbol: false }) : "0"}</b>
        <span>{currencyInfo(cur).symbol}</span>
      </div>

      <div className="quiet-row">
        <button type="button" className="link-btn" onClick={() => setSheet("account")}>
          {account?.name ?? "—"}
        </button>
        <button type="button" className="link-btn" onClick={() => setSheet("date")}>
          {dayLabel(lang, date, today)}
        </button>
        <button type="button" className="link-btn" onClick={() => setSheet("note")}>
          {note.trim() ? note.trim().slice(0, 18) + (note.trim().length > 18 ? "…" : "") : t.note}
        </button>
      </div>

      <div className="cat-grid">
        {gridCats.map(tile)}
        {cats.length > 8 && (
          <button type="button" className="cat-tile" aria-pressed={!!selectedOutsideGrid} onClick={() => setSheet("cats")}>
            <CatIcon
              category={selectedOutsideGrid ? cats.find((c) => c.id === categoryId) : null}
              selected={!!selectedOutsideGrid}
              size={46}
            />
            <span>{selectedOutsideGrid ? cats.find((c) => c.id === categoryId)?.name : t.more}</span>
          </button>
        )}
      </div>

      {frequent.length > 0 && !input && (
        <div className="field">
          <span className="hint small" style={{ paddingLeft: 4 }}>
            {t.frequent}
          </span>
          <div className="chips">
            {frequent.map((f, i) => (
              <button key={i} type="button" className="quick-chip num" onClick={() => save(f)}>
                {f.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="push-bottom" />
      <Numpad allowComma={currencyInfo(cur).exponent > 0} onKey={(k) => setInput((s) => pressKey(s, k, cur))} />

      <button
        type="button"
        className="btn btn-primary"
        disabled={busy || amount <= 0 || !categoryId || !account}
        onClick={() => save()}
      >
        {amount > 0 && !categoryId ? t.pickCategory : t.save}
      </button>
      {tx && (
        <button type="button" className="btn btn-danger" onClick={remove} disabled={busy}>
          {t.delete}
        </button>
      )}

      <Sheet open={sheet === "account"} onClose={() => setSheet(null)} label={t.accounts}>
        {active
          .filter((a) => !tx || a.currency === (accounts.find((x) => x.id === tx.account_id)?.currency ?? a.currency))
          .map((a) => (
            <button
              key={a.id}
              type="button"
              className="option"
              onClick={() => {
                setAccountId(a.id);
                setSheet(null);
              }}
            >
              <span>{a.name}</span>
              <span className="hint num">{formatMoney(a.balance, a.currency)}</span>
            </button>
          ))}
      </Sheet>

      <Sheet open={sheet === "date"} onClose={() => setSheet(null)} label={t.otherDate}>
        {[today, yesterday].map((d) => (
          <button
            key={d.toDateString()}
            type="button"
            className="option"
            onClick={() => {
              setDate(new Date(noonOf(d)));
              setDateTouched(true);
              setSheet(null);
            }}
          >
            {dayLabel(lang, d, today)}
          </button>
        ))}
        <label className="field">
          <span className="hint">{t.otherDate}</span>
          <input
            className="input"
            type="date"
            max={localDateInput(today)}
            min="2000-01-01"
            value={localDateInput(date)}
            onChange={(e) => {
              if (!e.target.value) return;
              const [y, m, d] = e.target.value.split("-").map(Number);
              setDate(new Date(noonOf(new Date(y, m - 1, d))));
              setDateTouched(true);
            }}
          />
        </label>
        <button type="button" className="btn btn-primary" onClick={() => setSheet(null)}>
          {t.done}
        </button>
      </Sheet>

      <Sheet open={sheet === "note"} onClose={() => setSheet(null)} label={t.note}>
        <label className="field">
          <span className="hint">{t.note}</span>
          <input
            className="input"
            value={note}
            maxLength={140}
            placeholder={t.notePlaceholder}
            autoFocus
            onChange={(e) => setNote(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && setSheet(null)}
          />
        </label>
        <button type="button" className="btn btn-primary" onClick={() => setSheet(null)}>
          {t.done}
        </button>
      </Sheet>

      <Sheet open={sheet === "cats"} onClose={() => setSheet(null)} label={t.categories}>
        <div className="cat-grid">{cats.map(tile)}</div>
      </Sheet>
    </main>
  );
}
