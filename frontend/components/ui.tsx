"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const LINKS = [
  { href: "/", label: "Wallet" },
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
