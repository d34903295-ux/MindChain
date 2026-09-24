"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

const LINKS = [
  { href: "/watch", label: "Vigilancia" },
  { href: "/wallet", label: "Wallet" },
  { href: "/contract", label: "Contrato" },
];

export function SiteHeader() {
  const path = usePathname();
  return (
    <header className="site-header">
      <nav aria-label="Principal" className="container nav-row">
        <Link href="/" className="brand">
          <span className="brand-mark" aria-hidden="true">
            CM
          </span>
          <span className="brand-name">ChainMind</span>
        </Link>
        <ul className="nav-list">
          {LINKS.map(l => (
            <li key={l.href}>
              <Link href={l.href} aria-current={path === l.href ? "page" : undefined}>
                {l.label}
              </Link>
            </li>
          ))}
          <li>
            <Link href="/watch" className="btn nav-cta">
              Empezar
            </Link>
          </li>
        </ul>
      </nav>
    </header>
  );
}

export type Tone = "ok" | "warn" | "bad" | "neutral";

export function riskTone(score: number): Tone {
  if (score < 30) return "ok";
  if (score < 70) return "warn";
  return "bad";
}

const TONE_VAR: Record<Tone, string> = {
  ok: "var(--ok)",
  warn: "var(--warn)",
  bad: "var(--bad)",
  neutral: "var(--muted)",
};

export function ScoreBar({ value, label }: { value: number; label: string }) {
  const tone = riskTone(value);
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <strong>{label}</strong>
        <strong style={{ color: TONE_VAR[tone] }}>
          {value}/100
        </strong>
      </div>
      <div
        className="score-track"
        role="progressbar"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        <div className="score-fill" style={{ width: `${value}%`, background: TONE_VAR[tone] }} />
      </div>
    </div>
  );
}

export function Chip({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  const cls = tone === "neutral" ? "chip" : `chip chip-${tone}`;
  return <span className={cls}>{children}</span>;
}

export function Stat({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="stat">
      <dt>{term}</dt>
      <dd>{children}</dd>
    </div>
  );
}

const ARC = Math.PI * 56;

export function RiskGauge({ value, label }: { value: number; label: string }) {
  const toneName = riskTone(value);
  const filled = Math.max(0, Math.min(100, value)) / 100;
  return (
    <div
      className="gauge-wrap"
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
    >
      <svg width="132" height="76" viewBox="0 0 132 76" aria-hidden="true">
        <path
          d="M 10 66 A 56 56 0 0 1 122 66"
          fill="none"
          stroke="var(--surface)"
          strokeWidth="11"
          strokeLinecap="round"
        />
        <path
          d="M 10 66 A 56 56 0 0 1 122 66"
          fill="none"
          stroke="var(--border)"
          strokeWidth="1"
          strokeDasharray="0"
        />
        <path
          d="M 10 66 A 56 56 0 0 1 122 66"
          fill="none"
          stroke={TONE_VAR[toneName]}
          strokeWidth="11"
          strokeLinecap="round"
          strokeDasharray={`${(filled * ARC).toFixed(1)} ${ARC.toFixed(1)}`}
        />
        <text
          x="66"
          y="60"
          textAnchor="middle"
          fill={TONE_VAR[toneName]}
          style={{ font: "700 26px var(--font-sans), system-ui, sans-serif" }}
        >
          {value}
        </text>
      </svg>
      <div>
        <div style={{ fontSize: "0.8125rem", fontWeight: 600, letterSpacing: "0.02em" }}>{label}</div>
        <div style={{ fontSize: "0.8125rem", color: "var(--muted)" }}>
          {value < 30 ? "Riesgo bajo" : value < 70 ? "Riesgo medio" : "Riesgo alto"} · 0–100
        </div>
      </div>
    </div>
  );
}

export function CopyButton({ text, label }: { text: string; label: string }) {
  const [done, setDone] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setDone(true);
      setTimeout(() => setDone(false), 2000);
    } catch {
      setDone(false);
    }
  };
  return (
    <>
      <button type="button" className="copy-btn" onClick={copy} aria-label={`Copiar ${label}`}>
        {done ? "Copiado" : "Copiar dirección"}
      </button>
      <span aria-live="polite" className="sr-only">
        {done ? `${label} copiada al portapapeles` : ""}
      </span>
    </>
  );
}

export function Skeleton({ label }: { label: string }) {
  return (
    <div role="status" aria-label={label} style={{ display: "grid", gap: "0.5rem", marginBlockStart: "1rem" }}>
      <div className="skeleton" style={{ height: "2.5rem", width: "60%" }} />
      <div className="skeleton" style={{ height: "5rem" }} />
      <div className="skeleton" style={{ height: "5rem" }} />
    </div>
  );
}
