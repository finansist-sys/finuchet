// Category colours: a CVD-validated categorical palette (fixed slot order), stepped per theme.
// A category keeps its slot everywhere (icon circle, donut segment, legend dot).

const LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"];
const DARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#0ca30c", "#9085e9", "#e66767"];
const GREY = { light: "#b3b9c1", dark: "#56667a" };

export type Scheme = "light" | "dark";

export function slotColor(slot: number, scheme: Scheme): string {
  if (slot < 0 || slot > 7) return GREY[scheme];
  return (scheme === "dark" ? DARK : LIGHT)[slot];
}

/** Soft tinted background for the icon circle. */
export function slotTint(slot: number, scheme: Scheme): string {
  return slotColor(slot, scheme) + (scheme === "dark" ? "33" : "1f");
}
