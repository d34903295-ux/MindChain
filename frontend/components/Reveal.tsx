"use client";

import { useEffect, useRef, type ReactNode } from "react";

/** Revelado por scroll (IntersectionObserver). Sin JS o sin IO: visible. */
export function Reveal({
  children,
  label,
  className = "reveal landing-section",
}: {
  children: ReactNode;
  label: string;
  className?: string;
}) {
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || !("IntersectionObserver" in window)) return;
    const io = new IntersectionObserver(
      entries => {
        for (const e of entries) {
          if (e.isIntersecting) {
            e.target.classList.add("revealed");
            io.unobserve(e.target);
          }
        }
      },
      { threshold: 0.12 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <section ref={ref} aria-label={label} className={className}>
      {children}
    </section>
  );
}
