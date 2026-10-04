import { useState } from "react";
import { CATEGORY_ICONS, Icon } from "../components/Icon";
import { CatIcon, Segmented, Sheet } from "../components/ui";
import { api, type Kind, type Me } from "../lib/api";
import { currencyInfo } from "../lib/money";
import { haptic } from "../lib/telegram";
import { useStore } from "../store";

export function Settings() {
  const { t, me, currencies, push, setMe, reload, resetTo, showToast, showError } = useStore();
  const [sheet, setSheet] = useState<"currency" | "delete" | null>(null);
  const base = me?.onboarded ? me.base_currency : "RUB";

  async function setBase(code: string) {
    try {
      setMe(await api.patch<Me>("/api/me", { base_currency: code }));
      setSheet(null);
      haptic.success();
    } catch (e) {
      showError(e);
    }
  }

  async function deleteAll() {
    try {
      await api.del("/api/me");
      haptic.success();
      setSheet(null);
      showToast(t.deleteAllDone);
      resetTo({ name: "home" });
      await reload();
    } catch (e) {
      showError(e);
    }
  }

  const rows: { icon: string; label: string; value?: string; onClick: () => void }[] = [
    { icon: "card", label: t.accounts, onClick: () => push({ name: "accounts" }) },
    { icon: "tag", label: t.categories, onClick: () => push({ name: "categories" }) },
    { icon: "cash", label: t.baseCurrency, value: `${currencyInfo(base).symbol} ${base}`, onClick: () => setSheet("currency") },
    { icon: "shield", label: t.privacy, onClick: () => push({ name: "privacy" }) },
  ];

  return (
    <main className="screen">
      <h1 className="h1">{t.settings}</h1>
      <section className="card" style={{ padding: "6px 16px" }}>
        {rows.map((r) => (
          <button key={r.label} type="button" className="option" onClick={r.onClick}>
            <span className="row">
              <Icon name={r.icon} color="var(--link)" />
              <span>{r.label}</span>
            </span>
            <span className="row hint">
              {r.value}
              <Icon name="right" size={18} />
            </span>
          </button>
        ))}
      </section>
      <button type="button" className="btn btn-danger" onClick={() => setSheet("delete")}>
        {t.deleteAll}
      </button>

      <Sheet open={sheet === "currency"} onClose={() => setSheet(null)} label={t.baseCurrency}>
        <h2 className="title">{t.baseCurrency}</h2>
        <div className="cat-grid">
          {currencies.map((c) => (
            <button
              key={c.code}
              type="button"
              className="chip"
              style={{ background: "var(--page)" }}
              aria-pressed={c.code === base}
              onClick={() => setBase(c.code)}
            >
              {c.symbol} {c.code}
            </button>
          ))}
        </div>
      </Sheet>

      <Sheet open={sheet === "delete"} onClose={() => setSheet(null)} label={t.deleteAll}>
        <p style={{ margin: 0 }}>{t.deleteAllConfirm}</p>
        <button type="button" className="btn btn-primary" style={{ background: "var(--danger)" }} onClick={deleteAll}>
          {t.deleteAll}
        </button>
        <button type="button" className="btn btn-tonal" onClick={() => setSheet(null)}>
          {t.cancel}
        </button>
      </Sheet>
    </main>
  );
}

export function Categories() {
  const { t, categories, reloadCategories, showError } = useStore();
  const [kind, setKind] = useState<Kind>("expense");
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [icon, setIcon] = useState("dots");
  const list = categories.filter((c) => c.kind === kind);

  async function toggle(id: string, archived: boolean) {
    try {
      await api.patch(`/api/categories/${id}`, { archived });
      await reloadCategories();
    } catch (e) {
      showError(e);
    }
  }

  async function add() {
    try {
      await api.post("/api/categories", { name: name.trim(), kind, icon, emoji: "•", color: list.length % 8 });
      await reloadCategories();
      haptic.success();
      setAdding(false);
      setName("");
      setIcon("dots");
    } catch (e) {
      showError(e);
    }
  }

  return (
    <main className="screen">
      <h1 className="h1">{t.categories}</h1>
      <Segmented
        options={[
          { value: "expense", label: t.expenses },
          { value: "income", label: t.incomes },
        ]}
        value={kind}
        onChange={setKind}
      />
      <section className="card" style={{ padding: "6px 16px" }}>
        {list.map((c) => (
          <div key={c.id} className="option" style={{ opacity: c.archived ? 0.5 : 1 }}>
            <span className="row">
              <CatIcon category={c} size={36} />
              <span>{c.name}</span>
            </span>
            <button type="button" className="link-btn" onClick={() => toggle(c.id, !c.archived)}>
              {c.archived ? t.show : t.hide}
            </button>
          </div>
        ))}
      </section>
      <button type="button" className="btn btn-tonal" onClick={() => setAdding(true)}>
        {t.addCategory}
      </button>

      <Sheet open={adding} onClose={() => setAdding(false)} label={t.addCategory}>
        <label className="field">
          <span className="hint">{t.name}</span>
          <input className="input" value={name} maxLength={32} onChange={(e) => setName(e.target.value)} />
        </label>
        <div className="cat-grid" style={{ gridTemplateColumns: "repeat(6, minmax(0, 1fr))" }}>
          {CATEGORY_ICONS.map((i) => (
            <button
              key={i}
              type="button"
              className="icon-btn"
              aria-label={i}
              aria-pressed={i === icon}
              style={{ background: i === icon ? "var(--tonal)" : "none" }}
              onClick={() => setIcon(i)}
            >
              <Icon name={i} />
            </button>
          ))}
        </div>
        <button type="button" className="btn btn-primary" disabled={!name.trim()} onClick={add}>
          {t.save}
        </button>
      </Sheet>
    </main>
  );
}

export function Privacy() {
  const { t } = useStore();
  return (
    <main className="screen">
      <h1 className="h1">{t.privacy}</h1>
      <section className="card">
        {t.privacyText.map((p) => (
          <p key={p} style={{ margin: 0, lineHeight: 1.5 }}>
            {p}
          </p>
        ))}
      </section>
    </main>
  );
}
