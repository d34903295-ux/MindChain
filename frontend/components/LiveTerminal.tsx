"use client";

import { API_BASE } from "../lib/api";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

type Row = {
  hash: string;
  value_eth: number;
  score: number;
  flags: string[];
};

const FALLBACK: Row[] = [
  { hash: "0x9fd170…f31f7d", value_eth: 0.42, score: 5, flags: ["limpia"] },
  { hash: "0x8f622d…068ea", value_eth: 1240, score: 45, flags: ["ballena", "outlier 20× mediana"] },
  { hash: "0x1ca171…b074d2", value_eth: 0, score: 65, flags: ["mezclador conocido"] },
];

function short(h: string): string {
  return h.length > 18 ? `${h.slice(0, 8)}…${h.slice(-6)}` : h;
}

function tone(score: number): string {
  if (score >= 50) return "var(--bad)";
  if (score >= 20) return "var(--warn)";
  return "var(--ok)";
}

/** Terminal del hero con datos REALES del feed + auto-refresh. */
export function LiveTerminal() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [block, setBlock] = useState<number | null>(null);
  const [live, setLive] = useState(false);
  const frame = useRef<HTMLDivElement>(null);

  const glow = (e: React.MouseEvent) => {
    const el = frame.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    el.style.setProperty("--mx", `${e.clientX - r.left}px`);
    el.style.setProperty("--my", `${e.clientY - r.top}px`);
  };

  useEffect(() => {
    let alive = true;
    let id: ReturnType<typeof setInterval> | undefined;
    const tick = () => {
      fetch("${API_BASE}/feed/ethereum?max_blocks=1")
        .then(r => (r.ok ? r.json() : Promise.reject()))
        .then(j => {
          if (!alive) return;
          const top = (j.txs as Row[]).slice(0, 3);
          if (top.length > 0) {
            setRows(top);
            setBlock(j.latest);
            setLive(true);
          }
        })
        .catch(() => undefined);
    };
    tick();
    id = setInterval(tick, 20000);
    return () => {
      alive = false;
      if (id) clearInterval(id);
    };
  }, []);

  const data = rows ?? FALLBACK;

  return (
    <div className="glow-frame" ref={frame} onMouseMove={glow}>
    <figure className="terminal terminal-live" aria-label="Transacciones analizadas en vivo" style={{ margin: 0 }}>
      <div className="terminal-bar" aria-hidden="true">
        <i />
        <i />
        <i />
        <span style={{ marginInlineStart: "0.5rem" }}>
          chainmind — feed en vivo{block ? ` · bloque ${block}` : ""}
        </span>
        {live && (
          <span className="ticker" style={{ marginInlineStart: "auto", border: "none", padding: 0 }}>
            <span className="dot live" aria-hidden="true" />
          </span>
        )}
      </div>
      <div aria-live="off">
        {data.map(s => (
          <div className="terminal-row" key={s.hash}>
            <span>{short(s.hash)}</span>
            <span>
              {s.value_eth} ETH ·{" "}
              <span className="score-num" style={{ color: tone(s.score) }}>
                {s.score}
              </span>
            </span>
            <span className="flags">{s.flags.join(", ")}</span>
          </div>
        ))}
      </div>
      <figcaption
        style={{ padding: "0.625rem 1rem", borderBlockStart: "1px solid var(--border)", fontSize: "0.75rem", color: "var(--muted)" }}
      >
        {live ? "Datos reales de Ethereum — " : "Conectando… ejemplo — "}
        <Link href="/watch">abrir vigilancia</Link>.
      </figcaption>
    </figure>
    </div>
  );
}
