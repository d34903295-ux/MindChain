"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

const LINKS = [
  { href: "/wallet", label: "Wallet" },
  { href: "/contract", label: "Contrato" },
  { href: "/watch", label: "Vigilancia" },
];

export function SiteHeader() {
  const path = usePathname();
  return (
    <header className="site-header">
      <nav aria-label="Principal" className="container nav-row">
        <Link href="/" className="brand">
          ChainMind
        </Link>
        <ul className="nav-list">
          {LINKS.map(l => (
            <li key={l.href}>
              <Link href={l.href} aria-current={path === l.href ? "page" : undefined}>
                {l.label}
              </Link>
            </li>
          ))}
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

const ARC = Math.PI * 52;

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
      <svg width="120" height="68" viewBox="0 0 120 68" aria-hidden="true">
        <path d="M 8 60 A 52 52 0 0 1 112 60" fill="none" stroke="var(--border)" strokeWidth="10" strokeLinecap="round" />
        <path
          d="M 8 60 A 52 52 0 0 1 112 60"
          fill="none"
          stroke={TONE_VAR[toneName]}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={`${(filled * ARC).toFixed(1)} ${ARC.toFixed(1)}`}
        />
      </svg>
      <div>
        <div className="gauge-num" style={{ color: TONE_VAR[toneName] }}>
          {value}
          <span style={{ fontSize: "1rem", color: "var(--muted)" }}>/100</span>
        </div>
        <div style={{ fontSize: "0.875rem", color: "var(--muted)" }}>{label}</div>
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
        {done ? "Copiado ✓" : "Copiar"}
      </button>
      <span aria-live="polite" className="mono" style={{ fontSize: "0.75rem", color: "var(--muted)" }}>
        {done ? "copiado al portapapeles" : ""}
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
