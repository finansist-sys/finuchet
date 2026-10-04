// Line icons (24px grid, 1.8 stroke). Category icon keys match the backend's ICONS set.

const PATHS: Record<string, string[]> = {
  cart: ["M2 3h3l2.7 12.2a1 1 0 0 0 1 .8h9.6a1 1 0 0 0 1-.8L21 7H6", "C9 20 1.5", "C18 20 1.5"],
  coffee: ["M4 8h13v5a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5z", "M17 9h1.5a2.5 2.5 0 0 1 0 5H17", "M8 2v3M12 2v3"],
  bus: ["R4 3 16 15 3", "M4 11h16M8 18v3M16 18v3"],
  phone: ["R7 2 10 20 2.5", "M11 18h2"],
  home: ["M3 11l9-7 9 7", "M5 10v10h14V10", "M10 20v-6h4v6"],
  heart: ["M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"],
  film: ["R3 5 18 14 2", "M7 5v14M17 5v14M3 12h18"],
  shirt: ["M8 3L3 6l2 4 3-1v12h8V9l3 1 2-4-5-3a4 4 0 0 1-8 0z"],
  dots: ["C6 12 1.3", "C12 12 1.3", "C18 12 1.3"],
  briefcase: ["R3 7 18 13 2", "M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M3 13h18"],
  gift: ["R3 8 18 4 1", "M5 12v8h14v-8M12 8v12", "M12 8S10.5 3.5 8 4.5 9 8 12 8zM12 8s1.5-4.5 4-3.5S15 8 12 8z"],
  car: ["M5 16V11l2-5h10l2 5v5", "M3 16h18v3H3z", "C7.5 13.5 1", "C16.5 13.5 1"],
  plane: ["M10 14l-7-2 1-2 7 1 4-7h2l-2 8 5 1 1-2h1.5l-1 4 1 4H22l-1-2-5 1 2 8h-2l-4-7"],
  book: ["M4 4h6a2 2 0 0 1 2 2v14a2 2 0 0 0-2-2H4z", "M20 4h-6a2 2 0 0 0-2 2v14a2 2 0 0 1 2-2h6z"],
  paw: ["C7 10 1.6", "C17 10 1.6", "C9.5 6 1.6", "C14.5 6 1.6", "M8 17c0-3 2-5 4-5s4 2 4 5c0 2-2 2-4 1.5C10 19 8 19 8 17z"],
  baby: ["C12 11 7", "M9.5 10h.01M14.5 10h.01", "M10 14c1.2 1 2.8 1 4 0"],
  dumbbell: ["M6 7v10M18 7v10M3 9v6M21 9v6M6 12h12"],
  pizza: ["M12 3L3 20h18z", "M5.5 15h13", "C11 11 1", "C14 15.5 .8"],
  fuel: ["R4 3 10 18 1.5", "M4 10h10", "M14 7l4 3v8a1.5 1.5 0 0 0 3 0V9l-3-3"],
  card: ["R2.5 5 19 14 2.5", "M2.5 10h19"],
  cash: ["R2.5 6 19 12 2", "C12 12 2.5"],
  percent: ["M19 5L5 19", "C7 7 2", "C17 17 2"],
  // UI
  chart: ["M4 20V10M10 20V4M16 20v-7M22 20H2"],
  gear: ["C12 12 3", "M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"],
  left: ["M15 6l-6 6 6 6"],
  right: ["M9 6l6 6-6 6"],
  back: ["M20 12H5M11 5l-7 7 7 7"],
  plus: ["M12 5v14M5 12h14"],
  swap: ["M7 4L3 8l4 4M3 8h14M17 20l4-4-4-4M21 16H7"],
  check: ["M5 12l5 5L20 7"],
  shield: ["M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"],
  trash: ["M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"],
  list: ["M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"],
  tag: ["M3 12V3h9l9 9-9 9z", "C7.5 7.5 1.2"],
  backspace: ["M21 5H8l-6 7 6 7h13z", "M11 9l6 6M17 9l-6 6"],
};

export const CATEGORY_ICONS = [
  "cart", "coffee", "bus", "phone", "home", "heart", "film", "shirt", "car", "plane", "book", "paw",
  "baby", "dumbbell", "pizza", "fuel", "briefcase", "gift", "card", "cash", "percent", "dots",
];

type Props = { name: string; size?: number; color?: string; strokeWidth?: number };

export function Icon({ name, size = 20, color = "currentColor", strokeWidth = 1.8 }: Props) {
  const parts = PATHS[name] ?? PATHS.dots;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {parts.map((p, i) => {
        if (p.startsWith("C")) {
          const [cx, cy, r] = p.slice(1).trim().split(/\s+/).map(Number);
          return <circle key={i} cx={cx} cy={cy} r={r} />;
        }
        if (p.startsWith("R")) {
          const [x, y, w, h, rx] = p.slice(1).trim().split(/\s+/).map(Number);
          return <rect key={i} x={x} y={y} width={w} height={h} rx={rx} />;
        }
        return <path key={i} d={p} />;
      })}
    </svg>
  );
}
