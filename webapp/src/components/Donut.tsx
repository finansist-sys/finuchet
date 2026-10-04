// Ring chart: segments in data order, 3-unit gaps between them, starting at 12 o'clock.
import type { ReactNode } from "react";

export type Segment = { value: number; color: string; label: string };

const R = 80;
const C = 2 * Math.PI * R;
const GAP = 3;

export function Donut({ segments, center, ariaLabel }: { segments: Segment[]; center: ReactNode; ariaLabel: string }) {
  const total = segments.reduce((s, x) => s + x.value, 0);
  let offset = 0;
  return (
    <div className="donut">
      <svg width="220" height="220" viewBox="0 0 210 210" role="img" aria-label={ariaLabel}>
        <g transform="rotate(-90 105 105)" fill="none" strokeWidth="16">
          {total === 0 ? (
            <circle cx="105" cy="105" r={R} stroke="var(--track)" />
          ) : (
            segments.map((s, i) => {
              const len = (s.value / total) * C;
              const dash = Math.max(len - (segments.length > 1 ? GAP : 0), 0.5);
              const el = (
                <circle
                  key={i}
                  cx="105"
                  cy="105"
                  r={R}
                  stroke={s.color}
                  strokeDasharray={`${dash} ${C - dash}`}
                  strokeDashoffset={-offset}
                />
              );
              offset += len;
              return el;
            })
          )}
        </g>
      </svg>
      <div className="donut-center">{center}</div>
    </div>
  );
}
