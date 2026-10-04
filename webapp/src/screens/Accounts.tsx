import { useState } from "react";
import { Icon } from "../components/Icon";
import { Segmented, Sheet } from "../components/ui";
import { api, type Account } from "../lib/api";
import { currencyInfo, currencyLabel, formatMoney, parseInput, toInput } from "../lib/money";
import { haptic } from "../lib/telegram";
import { useStore } from "../store";

function cleanAmount(v: string, allowMinus = false): string {
  const s = v.replace(".", ",").replace(allowMinus ? /[^\d,-]/g : /[^\d,]/g, "");
  return allowMinus ? s.replace(/(?!^)-/g, "") : s;
}

function parseSigned(v: string, cur: string): number {
  const neg = v.startsWith("-");
  const n = parseInput(v.replace("-", ""), cur);
  return neg ? -n : n;
}

export function Accounts() {
  const { t, me, accounts, currencies, reloadAccounts, bump, showToast, showError } = useStore();
  const base = me?.onboarded ? me.base_currency : "RUB";
  const active = accounts.filter((a) => !a.archived);
  const [edit, setEdit] = useState<Account | null>(null);
  const [name, setName] = useState("");
  const [actual, setActual] = useState("");
  const [adding, setAdding] = useState(false);
  const [newType, setNewType] = useState<"card" | "cash">("card");
  const [newName, setNewName] = useState("");
  const [newCur, setNewCur] = useState(base);
  const [newBalance, setNewBalance] = useState("");
  const [transfer, setTransfer] = useState(false);
  const [fromId, setFromId] = useState(active[0]?.id ?? "");
  const [toId, setToId] = useState(active[1]?.id ?? "");
  const [sent, setSent] = useState("");
  const [got, setGot] = useState("");
  const [busy, setBusy] = useState(false);

  async function run(fn: () => Promise<unknown>, done: string) {
    if (busy) return;
    setBusy(true);
    try {
      await fn();
      await reloadAccounts();
      bump();
      haptic.success();
      showToast(done);
      setEdit(null);
      setAdding(false);
      setTransfer(false);
    } catch (e) {
      showError(e);
    } finally {
      setBusy(false);
    }
  }

  function openEdit(a: Account) {
    setEdit(a);
    setName(a.name);
    setActual(toInput(a.balance, a.currency).replace(/^/, a.balance < 0 ? "-" : ""));
  }

  const from = active.find((a) => a.id === fromId);
  const to = active.find((a) => a.id === toId);
  const cross = from && to && from.currency !== to.currency;
  const curOptions = [base, ...currencies.map((c) => c.code).filter((c) => c !== base)].slice(0, 16);

  return (
    <main className="screen">
      <h1 className="h1">{t.accounts}</h1>
      <section className="card" style={{ padding: "6px 16px" }}>
        {active.map((a) => (
          <button key={a.id} type="button" className="option" onClick={() => openEdit(a)}>
            <span className="row">
              <Icon name={a.type === "card" ? "card" : "cash"} color="var(--link)" />
              <span>{a.name}</span>
            </span>
            <span className="num" style={{ fontWeight: 500 }}>
              {formatMoney(a.balance, a.currency)}
            </span>
          </button>
        ))}
      </section>

      <div className="btn-row">
        <button type="button" className="btn btn-tonal" onClick={() => setAdding(true)}>
          {t.addAccount}
        </button>
        <button type="button" className="btn btn-tonal" disabled={active.length < 2} onClick={() => setTransfer(true)}>
          {t.transfer}
        </button>
      </div>

      {/* edit / reconcile / hide */}
      <Sheet open={edit !== null} onClose={() => setEdit(null)} label={edit?.name ?? ""}>
        {edit && (
          <>
            <label className="field">
              <span className="hint">{t.name}</span>
              <input className="input" value={name} maxLength={40} onChange={(e) => setName(e.target.value)} />
            </label>
            <label className="field">
              <span className="hint">{t.reconcileHint}</span>
              <input
                className="input num"
                inputMode="decimal"
                value={actual}
                maxLength={18}
                onChange={(e) => setActual(cleanAmount(e.target.value, true))}
              />
            </label>
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy || !name.trim()}
              onClick={() =>
                run(async () => {
                  if (name.trim() !== edit.name) await api.patch(`/api/accounts/${edit.id}`, { name: name.trim() });
                  const target = parseSigned(actual, edit.currency);
                  if (target !== edit.balance) await api.post(`/api/accounts/${edit.id}/reconcile`, { balance: target });
                }, t.saved)
              }
            >
              {t.save}
            </button>
            <button
              type="button"
              className="btn btn-danger"
              disabled={busy || active.length < 2}
              onClick={() => run(() => api.patch(`/api/accounts/${edit.id}`, { archived: true }), t.saved)}
            >
              {t.archive}
            </button>
          </>
        )}
      </Sheet>

      {/* add account */}
      <Sheet open={adding} onClose={() => setAdding(false)} label={t.addAccount}>
        <Segmented
          options={[
            { value: "card", label: t.card },
            { value: "cash", label: t.cash },
          ]}
          value={newType}
          onChange={setNewType}
        />
        <label className="field">
          <span className="hint">{t.name}</span>
          <input
            className="input"
            value={newName}
            maxLength={40}
            placeholder={newType === "card" ? t.card : t.cash}
            onChange={(e) => setNewName(e.target.value)}
          />
        </label>
        <div className="field">
          <span className="hint">{t.currency}</span>
          <div className="chips">
            {curOptions.map((c) => (
              <button
                key={c}
                type="button"
                className="chip"
                style={{ background: "var(--page)" }}
                aria-pressed={c === newCur}
                onClick={() => setNewCur(c)}
              >
                {currencyLabel(c)}
              </button>
            ))}
          </div>
        </div>
        <label className="field">
          <span className="hint">{t.startBalance}</span>
          <input
            className="input num"
            inputMode="decimal"
            value={newBalance}
            maxLength={16}
            onChange={(e) => setNewBalance(cleanAmount(e.target.value))}
          />
        </label>
        <button
          type="button"
          className="btn btn-primary"
          disabled={busy}
          onClick={() =>
            run(
              () =>
                api.post("/api/accounts", {
                  type: newType,
                  name: newName.trim() || (newType === "card" ? t.card : t.cash),
                  currency: newCur,
                  balance: parseInput(newBalance, newCur),
                }),
              t.saved,
            )
          }
        >
          {t.save}
        </button>
      </Sheet>

      {/* transfer */}
      <Sheet open={transfer} onClose={() => setTransfer(false)} label={t.transfer}>
        {[
          { label: t.from, value: fromId, set: setFromId },
          { label: t.to, value: toId, set: setToId },
        ].map((f) => (
          <div className="field" key={f.label}>
            <span className="hint">{f.label}</span>
            <div className="chips">
              {active.map((a) => (
                <button
                  key={a.id}
                  type="button"
                  className="chip"
                  style={{ background: "var(--page)" }}
                  aria-pressed={a.id === f.value}
                  onClick={() => f.set(a.id)}
                >
                  {a.name}
                </button>
              ))}
            </div>
          </div>
        ))}
        <label className="field">
          <span className="hint">
            {t.extraAmount}
            {from ? `, ${currencyInfo(from.currency).symbol}` : ""}
          </span>
          <input className="input num" inputMode="decimal" value={sent} maxLength={16} onChange={(e) => setSent(cleanAmount(e.target.value))} />
        </label>
        {cross && to && (
          <label className="field">
            <span className="hint">
              {t.received}, {currencyInfo(to.currency).symbol}
            </span>
            <input className="input num" inputMode="decimal" value={got} maxLength={16} onChange={(e) => setGot(cleanAmount(e.target.value))} />
          </label>
        )}
        <button
          type="button"
          className="btn btn-primary"
          disabled={busy || !from || !to || from.id === to.id || parseInput(sent, from?.currency ?? base) <= 0 || (!!cross && parseInput(got, to?.currency ?? base) <= 0)}
          onClick={() =>
            from &&
            to &&
            run(
              () =>
                api.post("/api/transactions", {
                  kind: "transfer",
                  account_id: from.id,
                  to_account_id: to.id,
                  amount: parseInput(sent, from.currency),
                  ...(cross ? { to_amount: parseInput(got, to.currency) } : {}),
                }),
              t.saved,
            )
          }
        >
          {t.transfer}
        </button>
      </Sheet>
    </main>
  );
}
