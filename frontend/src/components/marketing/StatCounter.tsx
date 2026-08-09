"use client";

import { useEffect, useState } from "react";
import { useInView, useReducedMotion } from "motion/react";
import { useRef } from "react";

export function StatCounter({
  value,
  label,
  suffix = "",
}: {
  value: number | null;
  label: string;
  suffix?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true });
  const reduce = useReducedMotion();
  const [n, setN] = useState(0);

  useEffect(() => {
    if (!inView || value === null) return;
    if (reduce) {
      setN(value);
      return;
    }
    const start = performance.now();
    const duration = 900;
    let frame = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setN(Math.round(value * eased));
      if (p < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [inView, value, reduce]);

  return (
    <div ref={ref} className="text-center">
      <p className="font-display text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
        {value === null ? "—" : n.toLocaleString()}
        {value === null ? "" : suffix}
      </p>
      <p className="mt-1 text-sm text-muted">{label}</p>
    </div>
  );
}
