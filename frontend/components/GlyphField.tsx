"use client";

import { useEffect, useRef } from "react";

const GLYPHS = "0123456789abcdef";
const COL_W = 22;
const FONT = "13px var(--font-mono), ui-monospace, monospace";

/** Lluvia de glifos hex sutil tras el hero. Se pausa fuera de vista y con reduced-motion. */
export function GlyphField() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf = 0;
    let running = true;
    let drops: { y: number; speed: number }[] = [];

    const resize = () => {
      const box = canvas.parentElement?.getBoundingClientRect();
      if (!box || box.width === 0) return;
      const d = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.floor(box.width * d);
      canvas.height = Math.floor(box.height * d);
      ctx.setTransform(d, 0, 0, d, 0, 0);
      ctx.font = FONT;
      const n = Math.max(1, Math.floor(box.width / COL_W));
      drops = Array.from({ length: n }, () => ({
        y: Math.random() * -box.height,
        speed: 0.6 + Math.random() * 1.4,
      }));
    };

    const frame = () => {
      raf = requestAnimationFrame(frame);
      if (!running) return;
      const w = canvas.width;
      const h = canvas.height;
      if (w === 0) return;
      const cssW = w / Math.min(window.devicePixelRatio || 1, 2);
      const cssH = h / Math.min(window.devicePixelRatio || 1, 2);
      ctx.clearRect(0, 0, cssW, cssH);
      drops.forEach((d, i) => {
        const x = i * COL_W + 6;
        for (let t = 0; t < 4; t++) {
          const yy = d.y - t * 18;
          if (yy < -20 || yy > cssH + 20) continue;
          const head = t === 0;
          ctx.fillStyle =
            head && Math.random() < 0.06
              ? "rgba(184, 240, 74, 0.5)"
              : `rgba(163, 163, 173, ${head ? 0.34 : 0.16 - t * 0.04})`;
          ctx.fillText(GLYPHS[Math.floor(Math.random() * GLYPHS.length)], x, yy);
        }
        d.y += d.speed;
        if (d.y - 4 * 18 > cssH + 20 && Math.random() < 0.02) d.y = -20;
      });
    };

    const io = new IntersectionObserver(
      entries => {
        running = entries[0]?.isIntersecting ?? true;
      },
      { threshold: 0 }
    );
    io.observe(canvas);
    resize();
    window.addEventListener("resize", resize);
    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      io.disconnect();
      window.removeEventListener("resize", resize);
    };
  }, []);

  return <canvas ref={ref} className="glyph-field" aria-hidden="true" />;
}
