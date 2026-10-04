import { useEffect, type ReactNode } from "react";
import type { Category } from "../lib/api";
import { slotColor, slotTint } from "../lib/palette";
import { haptic } from "../lib/telegram";
import { useStore } from "../store";
import { Icon } from "./Icon";

export function CatIcon({ category, selected = false, size = 40 }: { category?: Category | null; selected?: boolean; size?: number }) {
  const { scheme } = useStore();
  const slot = category?.color ?? -1;
  const color = slotColor(slot, scheme);
  return (
    <span
      className="cat-icon"
      style={{ width: size, height: size, background: selected ? color : slotTint(slot, scheme) }}
    >
      <Icon name={category?.icon ?? "dots"} color={selected ? "#ffffff" : color} />
    </span>
  );
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="seg" role="group">
      {options.map((o) => (
        <button key={o.value} type="button" aria-pressed={o.value === value} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", ",", "0", "⌫"];

export function Numpad({ onKey, allowComma = true }: { onKey: (k: string) => void; allowComma?: boolean }) {
  const { lang } = useStore();
  return (
    <div className="numpad">
      {KEYS.map((k) =>
        k === "," && !allowComma ? (
          <span key={k} />
        ) : (
          <button
            key={k}
            type="button"
            aria-label={k === "⌫" ? (lang === "ru" ? "Стереть" : "Delete") : k}
            onClick={() => {
              haptic.tap();
              onKey(k);
            }}
          >
            {k === "⌫" ? <Icon name="backspace" size={24} /> : k}
          </button>
        ),
      )}
    </div>
  );
}

export function Sheet({ open, onClose, children, label }: { open: boolean; onClose: () => void; children: ReactNode; label: string }) {
  useEffect(() => {
    if (!open) return;
    const onEsc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onEsc);
    return () => window.removeEventListener("keydown", onEsc);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet" role="dialog" aria-modal="true" aria-label={label} onClick={(e) => e.stopPropagation()}>
        {children}
      </div>
    </div>
  );
}

export function ToastView() {
  const { toast } = useStore();
  if (!toast) return null;
  return (
    <div className="toast" role="status" key={toast.id}>
      <span>{toast.text}</span>
      {toast.action && (
        <button type="button" onClick={toast.action.run}>
          {toast.action.label}
        </button>
      )}
    </div>
  );
}

export function Skeleton({ height }: { height: number }) {
  return <div className="skeleton" style={{ height }} aria-hidden="true" />;
}
