import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, ApiError, type Account, type Category, type Currency, type Kind, type Me, type Tx } from "./lib/api";
import { dicts, langOf, type Lang } from "./lib/i18n";
import { registerCurrencies } from "./lib/money";
import type { Scheme } from "./lib/palette";
import { haptic, initTelegram, setBackButton, telegramLanguage } from "./lib/telegram";

export type Route =
  | { name: "home" }
  | { name: "add"; kind: Kind; tx?: Tx }
  | { name: "history"; categoryId?: string }
  | { name: "analytics" }
  | { name: "accounts" }
  | { name: "settings" }
  | { name: "categories" }
  | { name: "privacy" };

type Toast = { id: number; text: string; action?: { label: string; run: () => void } };

type Store = {
  lang: Lang;
  t: (typeof dicts)["ru"];
  scheme: Scheme;
  me: Me | null;
  currencies: Currency[];
  accounts: Account[];
  categories: Category[];
  loadError: boolean;
  route: Route;
  push: (r: Route) => void;
  back: () => void;
  resetTo: (r: Route) => void;
  reload: () => Promise<void>;
  reloadAccounts: () => Promise<void>;
  reloadCategories: () => Promise<void>;
  setMe: (m: Me) => void;
  toast: Toast | null;
  showToast: (text: string, action?: Toast["action"]) => void;
  showError: (e: unknown) => void;
  dataVersion: number;
  bump: () => void;
};

const Ctx = createContext<Store | null>(null);

// Dev only (stripped from production builds): open a screen directly, e.g. ?screen=analytics
function initialStack(): Route[] {
  const home: Route = { name: "home" };
  if (!import.meta.env.DEV) return [home];
  const name = new URLSearchParams(location.search).get("screen");
  const simple = ["history", "analytics", "accounts", "settings", "categories", "privacy"];
  if (name === "add") return [home, { name: "add", kind: "expense" }];
  if (name && simple.includes(name)) return [home, { name } as Route];
  return [home];
}

export function useStore(): Store {
  const s = useContext(Ctx);
  if (!s) throw new Error("StoreProvider missing");
  return s;
}

export function StoreProvider({ children }: { children: ReactNode }) {
  const [scheme, setScheme] = useState<Scheme>("light");
  const [me, setMe] = useState<Me | null>(null);
  const [currencies, setCurrencies] = useState<Currency[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loadError, setLoadError] = useState(false);
  const [stack, setStack] = useState<Route[]>(initialStack);
  const [toast, setToast] = useState<Toast | null>(null);
  const [dataVersion, setDataVersion] = useState(0);
  const toastTimer = useRef<number | undefined>(undefined);

  const lang = langOf(me?.lang ?? telegramLanguage());
  const t = dicts[lang];

  useEffect(() => initTelegram(setScheme), []);

  const reloadAccounts = useCallback(async () => setAccounts(await api.get<Account[]>("/api/accounts")), []);
  const reloadCategories = useCallback(async () => setCategories(await api.get<Category[]>("/api/categories")), []);

  const reload = useCallback(async () => {
    try {
      setLoadError(false);
      const [m, cur] = await Promise.all([api.get<Me>("/api/me"), api.get<Currency[]>("/api/currencies")]);
      registerCurrencies(cur);
      setCurrencies(cur);
      if (m.onboarded) await Promise.all([reloadAccounts(), reloadCategories()]);
      setMe(m);
    } catch {
      setLoadError(true);
    }
  }, [reloadAccounts, reloadCategories]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const push = useCallback((r: Route) => setStack((s) => [...s, r]), []);
  const back = useCallback(() => setStack((s) => (s.length > 1 ? s.slice(0, -1) : s)), []);
  const resetTo = useCallback((r: Route) => setStack([r]), []);
  const route = stack[stack.length - 1];

  useEffect(() => {
    setBackButton(stack.length > 1 ? back : null);
    window.scrollTo(0, 0);
  }, [stack.length, back]);

  const showToast = useCallback((text: string, action?: Toast["action"]) => {
    window.clearTimeout(toastTimer.current);
    setToast({ id: Date.now(), text, action });
    toastTimer.current = window.setTimeout(() => setToast(null), action ? 5000 : 2500);
  }, []);

  const showError = useCallback(
    (e: unknown) => {
      haptic.error();
      if (!(e instanceof ApiError)) return showToast(t.offline);
      const byCode: Record<string, string> = {
        card_number_not_allowed: t.cardNumber,
        too_many_requests: t.tooMany,
        reauth_required: t.reopenApp,
        unauthorized: t.reopenApp,
        onboarding_required: t.needOnboarding,
        invalid_request: t.invalid,
        amount_invalid: t.invalid,
        to_amount_required: t.invalid,
        name_required: t.invalid,
      };
      showToast(byCode[e.code] ?? t.error);
    },
    [showToast, t],
  );

  const value = useMemo<Store>(
    () => ({
      lang, t, scheme, me, currencies, accounts, categories, loadError, route, push, back, resetTo, reload,
      reloadAccounts, reloadCategories, setMe, toast, showToast, showError, dataVersion,
      bump: () => setDataVersion((v) => v + 1),
    }),
    [lang, t, scheme, me, currencies, accounts, categories, loadError, route, push, back, resetTo, reload,
      reloadAccounts, reloadCategories, toast, showToast, showError, dataVersion],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
