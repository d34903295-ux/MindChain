"use client";

import { useState } from "react";
import { Chip, CopyButton, RiskGauge, Skeleton, Stat, riskTone } from "../../components/ui";

type Report = {
  address: string;
  chain: string;
  profile: Record<string, unknown>;
  risk_score: number;
  risk_factors: string[];
  explanation: string;
  elapsed_s?: number;
  source?: string;
};

function str(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (Array.isArray(v)) return v.join(", ") || "—";
  return String(v);
}

export default function WalletPage() {
  const [addr, setAddr] = useState("0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045");
  const [chain, setChain] = useState("ethereum");
  const [res, setRes] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const analyze = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErr("");
    setRes(null);
    try {
      const r = await fetch("http://localhost:8000/analyze-wallet", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address: addr.trim(), chain }),
      });
      if (!r.ok) throw new Error(`El backend devolvió ${r.status}`);
      setRes(await r.json());
    } catch (e: unknown) {
      setErr(`No se pudo analizar. ¿Backend en :8000? ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main id="contenido" className="container page">
      <header className="page-head">
        <p className="eyebrow">Wallet Intelligence</p>
        <h1 className="page-title">Analiza una wallet</h1>
        <p className="section-lede">
          Perfil, score de riesgo y explicación en menos de 10 segundos. Los agentes Investigator,
          Risk y Explanation trabajan en paralelo.
        </p>
      </header>

      <form onSubmit={analyze} aria-label="Analizar wallet" aria-busy={loading}>
        <div className="field" style={{ maxWidth: "12rem" }}>
          <label htmlFor="chain">Red</label>
          <select id="chain" className="select" value={chain} onChange={e => setChain(e.target.value)}>
            <option value="ethereum">Ethereum</option>
            <option value="base">Base</option>
          </select>
        </div>
        <div className="field" style={{ marginBlockStart: "0.75rem" }}>
          <label htmlFor="addr">Dirección (0x + 40 caracteres hex)</label>
          <input
            id="addr"
            className="input input-mono"
            value={addr}
            onChange={e => setAddr(e.target.value)}
            placeholder="0x…"
            required
            minLength={42}
            maxLength={42}
            autoComplete="off"
            spellCheck={false}
          />
        </div>
        <button type="submit" className="btn" disabled={loading} style={{ marginBlockStart: "0.75rem" }}>
          {loading ? "Analizando…" : "Analizar"}
        </button>
      </form>

      {err && (
        <p role="alert" className="error-text">
          {err}
        </p>
      )}

      {loading && <Skeleton label="Analizando wallet" />}

      {res && (
        <section aria-live="polite" aria-label="Resultado del análisis" className="card">
          <div style={{ display: "flex", gap: "1rem", alignItems: "center", flexWrap: "wrap" }}>
            <figure style={{ margin: 0, textAlign: "center" }}>
              <img
                src={`http://localhost:8000/qr/${res.address}`}
                width={96}
                height={96}
                alt={`Código QR de la dirección ${res.address}`}
              />
              <figcaption style={{ fontSize: "0.75rem", color: "var(--muted)" }}>QR</figcaption>
            </figure>
            <div style={{ flex: "1 1 16rem" }}>
              <h2 className="mono" style={{ fontSize: "1rem", margin: 0, overflowWrap: "anywhere" }}>
                {res.address}
              </h2>
              <p style={{ color: "var(--muted)", fontSize: "0.875rem", margin: "0.25rem 0" }}>
                {res.chain} · {res.elapsed_s}s servidor · fuente {res.source} ·{" "}
                <a
                  href={`http://localhost:8000/report/${res.address}?chain=${chain}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Descargar reporte .md
                </a>
              </p>
              <CopyButton text={res.address} label="dirección" />
            </div>
          </div>

          <div style={{ marginBlockStart: "1rem" }}>
            <RiskGauge value={res.risk_score} label="Riesgo" />
            <div style={{ marginBlockStart: "0.75rem", display: "flex", gap: "0.375rem", flexWrap: "wrap" }}>
              {res.risk_factors.length === 0 ? (
                <Chip tone="ok">sin factores de riesgo</Chip>
              ) : (
                res.risk_factors.map(f => (
                  <Chip key={f} tone={riskTone(res.risk_score)}>
                    {f}
                  </Chip>
                ))
              )}
            </div>
          </div>

          <h3>Perfil</h3>
          <dl className="stat-grid">
            <Stat term="Txs lifetime">{str(res.profile.tx_count)}</Stat>
            <Stat term="Antigüedad (días)">{str(res.profile.age_days)}</Stat>
            <Stat term="Actividad">{str(res.profile.activity)}</Stat>
            <Stat term="Frec. tx/día">{str(res.profile.freq_tx_day)}</Stat>
            <Stat term="Balance USD">${Number(res.profile.balance_usd || 0).toLocaleString("es")}</Stat>
            <Stat term="Contrapartes (muestra)">{str(res.profile.counterparties_sample)}</Stat>
            <Stat term="Bot-like">{str(res.profile.bot_like)}</Stat>
            <Stat term="Etiquetas">{str(res.profile.labels)}</Stat>
          </dl>

          <h3>Explicación</h3>
          <p className="explainer">{res.explanation}</p>
        </section>
      )}
    </main>
  );
}
