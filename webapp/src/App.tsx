import { useEffect } from "react";
import { Icon } from "./components/Icon";
import { Skeleton, ToastView } from "./components/ui";
import { hasNativeBack } from "./lib/telegram";
import { Accounts } from "./screens/Accounts";
import { Add } from "./screens/Add";
import { Analytics } from "./screens/Analytics";
import { History } from "./screens/History";
import { Home } from "./screens/Home";
import { Onboarding } from "./screens/Onboarding";
import { Categories, Privacy, Settings } from "./screens/Settings";
import { useStore } from "./store";

function Screen() {
  const { me, route, loadError, reload, t } = useStore();

  if (loadError) {
    return (
      <main className="screen" style={{ justifyContent: "center" }}>
        <div className="empty">
          <b>{t.offline}</b>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => void reload()}>
          {t.next}
        </button>
      </main>
    );
  }
  if (!me) {
    return (
      <main className="screen">
        <Skeleton height={140} />
        <Skeleton height={120} />
      </main>
    );
  }
  if (!me.onboarded) return <Onboarding />;

  switch (route.name) {
    case "add":
      return <Add key={route.tx?.id ?? route.kind} kind={route.kind} tx={route.tx} />;
    case "history":
      return <History categoryId={route.categoryId} />;
    case "analytics":
      return <Analytics />;
    case "accounts":
      return <Accounts />;
    case "settings":
      return <Settings />;
    case "categories":
      return <Categories />;
    case "privacy":
      return <Privacy />;
    default:
      return <Home />;
  }
}

function BrowserBack() {
  const { route, me, back, t } = useStore();
  const visible = !hasNativeBack && route.name !== "home" && Boolean(me?.onboarded);
  useEffect(() => {
    document.documentElement.classList.toggle("has-browser-back", visible);
  }, [visible]);
  if (!visible) return null;
  return (
    <div className="browser-back">
      <button type="button" className="icon-btn" aria-label={t.cancel} onClick={back}>
        <Icon name="back" size={22} />
      </button>
    </div>
  );
}

export function App() {
  return (
    <>
      <BrowserBack />
      <Screen />
      <ToastView />
    </>
  );
}
