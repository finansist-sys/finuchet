import { useCallback, useEffect, useState } from "react";
import { TxRow } from "../components/TxRow";
import { Sheet, Skeleton } from "../components/ui";
import { api, type Tx } from "../lib/api";
import { dayLabel } from "../lib/i18n";
import { haptic } from "../lib/telegram";
import { useStore } from "../store";
import { openTx } from "./Home";

type Filter = "all" | "expense" | "income";
const PAGE = 50;

export function History({ categoryId }: { categoryId?: string }) {
  const { t, lang, push, dataVersion, bump, showToast, showError } = useStore();
  const [filter, setFilter] = useState<Filter>("all");
  const [items, setItems] = useState<Tx[] | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [selected, setSelected] = useState<Tx | null>(null);

  const load = useCallback(
    async (offset: number) => {
      const q = new URLSearchParams({ limit: String(PAGE), offset: String(offset) });
      if (filter !== "all") q.set("kind", filter);
      if (categoryId) q.set("category_id", categoryId);
      const res = await api.get<{ items: Tx[]; has_more: boolean }>(`/api/transactions?${q}`);
      setItems((prev) => (offset === 0 ? res.items : [...(prev ?? []), ...res.items]));
      setHasMore(res.has_more);
    },
    [filter, categoryId],
  );

  useEffect(() => {
    load(0).catch(showError);
  }, [load, dataVersion, showError]);

  async function removeSelected() {
    if (!selected) return;
    try {
      await api.del(`/api/transactions/${selected.id}`);
      haptic.success();
      setSelected(null);
      showToast(t.deleted);
      bump();
    } catch (e) {
      showError(e);
    }
  }

  const today = new Date();
  const groups: { label: string; items: Tx[] }[] = [];
  for (const tx of items ?? []) {
    const label = dayLabel(lang, new Date(tx.occurred_at), today);
    const last = groups[groups.length - 1];
    if (last && last.label === label) last.items.push(tx);
    else groups.push({ label, items: [tx] });
  }

  return (
    <main className="screen">
      <h1 className="h1">{t.history}</h1>
      <div className="chips">
        {(["all", "expense", "income"] as Filter[]).map((f) => (
          <button key={f} type="button" className="chip" aria-pressed={filter === f} onClick={() => setFilter(f)}>
            {f === "all" ? t.all : f === "expense" ? t.expenses : t.incomes}
          </button>
        ))}
      </div>

      {items === null ? (
        <>
          <Skeleton height={60} />
          <Skeleton height={60} />
          <Skeleton height={60} />
        </>
      ) : items.length === 0 ? (
        <div className="empty">
          <b>{t.emptyTitle}</b>
          <span className="hint">{t.emptyText}</span>
        </div>
      ) : (
        <section className="list">
          {groups.map((g) => (
            <div key={g.label}>
              <div className="day-head hint small">{g.label}</div>
              {g.items.map((tx) => (
                <TxRow
                  key={tx.id}
                  tx={tx}
                  onOpen={(x) => (x.kind === "expense" || x.kind === "income" ? openTx(x, push) : setSelected(x))}
                />
              ))}
            </div>
          ))}
          {hasMore && (
            <button type="button" className="btn btn-tonal" onClick={() => load(items.length).catch(showError)}>
              {t.showMore}
            </button>
          )}
        </section>
      )}

      <Sheet open={selected !== null} onClose={() => setSelected(null)} label={t.delete}>
        {selected && <TxRow tx={selected} onOpen={() => undefined} />}
        <button type="button" className="btn btn-danger" onClick={removeSelected}>
          {t.delete}
        </button>
        <button type="button" className="btn btn-tonal" onClick={() => setSelected(null)}>
          {t.cancel}
        </button>
      </Sheet>
    </main>
  );
}
