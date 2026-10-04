import type { Tx } from "../lib/api";
import { formatMoney } from "../lib/money";
import { useStore } from "../store";
import { Icon } from "./Icon";
import { CatIcon } from "./ui";

export function TxRow({ tx, onOpen }: { tx: Tx; onOpen: (tx: Tx) => void }) {
  const { t, accounts, categories } = useStore();
  const acc = accounts.find((a) => a.id === tx.account_id);
  const cur = acc?.currency ?? "RUB";
  const cat = categories.find((c) => c.id === tx.category_id) ?? null;

  let title: string;
  let amount: string;
  let cls = "amount num";
  if (tx.kind === "transfer") {
    const to = accounts.find((a) => a.id === tx.to_account_id);
    title = `${acc?.name ?? "—"} → ${to?.name ?? "—"}`;
    amount = formatMoney(tx.amount, cur);
  } else if (tx.kind === "adjustment") {
    title = t.adjustmentLabel;
    amount = formatMoney(tx.amount, cur, { signed: true });
  } else {
    title = cat?.name ?? t.noCategory;
    amount = formatMoney(tx.kind === "expense" ? -tx.amount : tx.amount, cur, { signed: true });
    if (tx.kind === "income") cls += " income";
  }
  const sub = [tx.note, tx.source === "bot" ? t.fromBot : null].filter(Boolean).join(" · ");

  return (
    <button type="button" className="list-row" onClick={() => onOpen(tx)}>
      {tx.kind === "transfer" || tx.kind === "adjustment" ? (
        <span className="cat-icon" style={{ background: "var(--tonal)", color: "var(--link)" }}>
          <Icon name={tx.kind === "transfer" ? "swap" : "check"} />
        </span>
      ) : (
        <CatIcon category={cat} />
      )}
      <span className="grow">
        <span>{title}</span>
        {sub && <span className="hint small">{sub}</span>}
      </span>
      <span className={cls}>{amount}</span>
    </button>
  );
}
