// Thin typed wrapper over window.Telegram.WebApp (loaded from telegram.org in index.html).
// Everything degrades gracefully in a normal browser (local development).

type Haptic = {
  impactOccurred(style: "light" | "medium" | "heavy" | "rigid" | "soft"): void;
  notificationOccurred(type: "error" | "success" | "warning"): void;
  selectionChanged(): void;
};

type BackButton = { show(): void; hide(): void; onClick(cb: () => void): void; offClick(cb: () => void): void };

type WebApp = {
  initData: string;
  initDataUnsafe: { user?: { language_code?: string } };
  colorScheme: "light" | "dark";
  version: string;
  ready(): void;
  expand(): void;
  isVersionAtLeast(v: string): boolean;
  disableVerticalSwipes?: () => void;
  enableVerticalSwipes?: () => void;
  enableClosingConfirmation?: () => void;
  disableClosingConfirmation?: () => void;
  onEvent(name: string, cb: () => void): void;
  HapticFeedback?: Haptic;
  BackButton?: BackButton;
};

declare global {
  interface Window {
    Telegram?: { WebApp?: WebApp };
  }
}

export const tg: WebApp | undefined = window.Telegram?.WebApp;

export function initTelegram(onThemeChange: (scheme: "light" | "dark") => void): void {
  const apply = () => {
    const scheme = tg?.colorScheme ?? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    document.documentElement.dataset.scheme = scheme;
    onThemeChange(scheme);
  };
  apply();
  if (!tg) return;
  tg.ready();
  tg.expand();
  tg.onEvent("themeChanged", apply);
}

/** initData proves to the server who the user is. In local dev without Telegram we send "dev". */
export function authHeader(): string {
  const data = tg?.initData;
  if (data) return `tma ${data}`;
  return import.meta.env.DEV ? "tma dev" : "";
}

export function telegramLanguage(): string {
  return tg?.initDataUnsafe.user?.language_code ?? navigator.language ?? "ru";
}

export const haptic = {
  success: () => tg?.HapticFeedback?.notificationOccurred("success"),
  error: () => tg?.HapticFeedback?.notificationOccurred("error"),
  tap: () => tg?.HapticFeedback?.selectionChanged(),
};

export function setVerticalSwipes(enabled: boolean): void {
  if (!tg?.isVersionAtLeast("7.7")) return;
  (enabled ? tg.enableVerticalSwipes : tg.disableVerticalSwipes)?.call(tg);
}

export function setClosingConfirmation(enabled: boolean): void {
  if (!tg?.isVersionAtLeast("6.2")) return;
  (enabled ? tg.enableClosingConfirmation : tg.disableClosingConfirmation)?.call(tg);
}

let backHandler: (() => void) | null = null;

export function setBackButton(handler: (() => void) | null): void {
  const bb = tg?.BackButton;
  if (!bb) return;
  if (backHandler) bb.offClick(backHandler);
  backHandler = handler;
  if (handler) {
    bb.onClick(handler);
    bb.show();
  } else {
    bb.hide();
  }
}
