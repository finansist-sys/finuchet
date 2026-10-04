import { authHeader } from "./telegram";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
  ) {
    super(code);
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: {
      Authorization: authHeader(),
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    credentials: "omit",
    cache: "no-store",
  });
  if (res.status === 204) return undefined as T;
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    /* empty body */
  }
  if (!res.ok) {
    const code = (data as { detail?: unknown } | null)?.detail;
    throw new ApiError(res.status, typeof code === "string" ? code : "error");
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, body),
  del: (path: string) => request<void>("DELETE", path),
};

// ---- API types (amounts are integers in minor units)

export type Kind = "expense" | "income";
export type TxKind = Kind | "transfer" | "adjustment";

export type Me =
  | { onboarded: false; lang: string; features: string[] }
  | {
      onboarded: true;
      base_currency: string;
      tz: string;
      lang: string;
      default_account_id: string | null;
      features: string[];
    };

export type Currency = { code: string; symbol: string; exponent: number };

export type Account = {
  id: string;
  name: string;
  type: "card" | "cash";
  currency: string;
  balance: number;
  archived: boolean;
};

export type Category = {
  id: string;
  name: string;
  kind: Kind;
  icon: string;
  emoji: string;
  color: number;
  archived: boolean;
};

export type Tx = {
  id: string;
  kind: TxKind;
  account_id: string;
  to_account_id: string | null;
  amount: number;
  to_amount: number | null;
  category_id: string | null;
  note: string | null;
  source: "bot" | "app";
  occurred_at: string;
};

export type Home = {
  currency: string;
  balances: Record<string, number>;
  month: { start: string; income: number; expense: number };
  week: { start: string; today_index: number; days: number[] };
  recent: Tx[];
};

export type CategoryStats = {
  currency: string;
  start: string;
  end: string;
  income: number;
  expense: number;
  categories: { category_id: string | null; amount: number }[];
};
