"use client";

import { useState } from "react";
import { Chip, CopyButton, RiskGauge, Skeleton, Stat, riskTone } from "../../components/ui";
import { ObsidianExport } from "../../components/ObsidianExport";

type AiInfo = {
  source?: "llm" | "determinista";
  provider?: string;
  model?: string;
  motivo?: string;
  latency_s?: number;
  cached?: boolean;
};

type Report = {
  address: string;
  chain: string;
  profile: Record<string, unknown>;
  risk_score: number | null;
  risk_factors: string[];
  explanation: string;
  ai?: AiInfo;
  elapsed_s?: number;
  source?: string;
  cached?: boolean;
  data_quality?: { degraded?: boolean; errors?: string[] };
};

function str(v: unknown): string {
  if (v === null || v === undefined) return "n/d";
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
          Perfil, score de riesgo y explicación en menos de 10 segundos. Los agentes Wallet, Research,
          Risk y Explanation trabajan en paralelo.
        </p>
      </header>

      <section className="card form-card" aria-label="Formulario de análisis">
        <form onSubmit={analyze} aria-label="Analizar wallet" aria-busy={loading}>
          <div className="form-row">
            <div className="field" style={{ maxWidth: "12rem" }}>
              <label htmlFor="chain">Red</label>
              <select id="chain" className="select" value={chain} onChange={e => setChain(e.target.value)}>
                <option value="ethereum">Ethereum</option>
                <option value="base">Base</option>
              </select>
            </div>
            <div className="field" style={{ flex: "1 1 22rem" }}>
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
            <button type="submit" className="btn" disabled={loading}>
              {loading ? "Analizando…" : "Analizar"}
            </button>
          </div>
          <p className="form-hint">
            Dato público de la cadena: no se guarda fuera de tu máquina. La IA que redacta la
            explicación se indica en cada respuesta (campo <code>ai</code>).
          </p>
        </form>

        {err && (
          <p role="alert" className="error-text">
            {err}
          </p>
        )}

        {loading && <Skeleton label="Analizando wallet" />}
      </section>

      {res && (
        <section aria-live="polite" aria-label="Resultado del análisis" className="card result-enter">
          <div className="result-head">
            <figure className="qr-frame" style={{ margin: 0 }}>
              <img
                src={`http://localhost:8000/qr/${res.address}`}
                width={104}
                height={104}
                alt={`Código QR de la dirección ${res.address}`}
              />
              <figcaption>QR de la wallet</figcaption>
            </figure>
            <div className="result-ident">
              <h2 className="mono result-addr">{res.address}</h2>
              <p className="result-meta">
                <span className="chip">{res.chain}</span>
                <span className="chip">{res.elapsed_s}s</span>
                <span className="chip">fuente {res.source}</span>
              </p>
              <p className="result-actions">
                <CopyButton text={res.address} label="dirección" />
                <a
                  className="btn btn-secondary"
                  href={`http://localhost:8000/report/${res.address}?chain=${chain}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Descargar reporte .md
                </a>
                <ObsidianExport address={res.address} chain={res.chain} kind="wallet" riskScore={res.risk_score} />
              </p>
            </div>
          </div>

          <div className="result-risk">
            <RiskGauge value={res.risk_score} label="Riesgo" />
            {res.risk_score !== null && (
              <div className="chip-row">
                {res.risk_factors.length === 0 ? (
                  <Chip tone="ok">sin factores de riesgo</Chip>
                ) : (
                  res.risk_factors.map(f => (
                    <Chip key={f} tone={riskTone(res.risk_score ?? 0)}>
                      {f}
                    </Chip>
                  ))
                )}
              </div>
            )}
            {res.data_quality?.errors && res.data_quality.errors.length > 0 && (
              <p className="data-warning" style={{ marginBlockStart: "0.75rem" }}>
                Fuente degradada: {res.data_quality.errors.join(" · ")}
              </p>
            )}
          </div>

          <h3>Perfil</h3>
          {res.profile.tx_count_reliable === false && (
            <p className="data-warning">
              El histórico de transacciones no es fiable en esta fuente: las métricas de
              frecuencia y antigüedad se omiten en lugar de estimar.
            </p>
          )}
          <dl className="stat-grid">
            <Stat term="Txs lifetime">{str(res.profile.tx_count)}</Stat>
            <Stat term="Antigüedad (días)">{str(res.profile.age_days)}</Stat>
            <Stat term="Actividad">{str(res.profile.activity)}</Stat>
            <Stat term="Frec. tx/día">{str(res.profile.freq_tx_day)}</Stat>
            <Stat term="Balance USD">${Number(res.profile.balance_usd || 0).toLocaleString("es")}</Stat>
            <Stat term="Contrapartes (muestra)">{str(res.profile.counterparties_sample)}</Stat>
            <Stat term="Muestra">
              {str(res.profile.sample_size)} · {str(res.profile.sample_confidence)}
            </Stat>
            <Stat term="Etiquetas">{str(res.profile.labels)}</Stat>
          </dl>

          <h3>Explicación</h3>
          <p className="explainer">{res.explanation}</p>
          {res.ai && (
            <p className="ai-note">
              {res.ai.source === "llm" ? (
                <>
                  Redactado por{" "}
                  <strong>
                    {res.ai.provider}
                    {res.ai.model ? ` · ${res.ai.model}` : ""}
                  </strong>
                  {res.ai.latency_s ? ` en ${res.ai.latency_s}s` : ""}
                  {res.ai.cached ? " (respuesta en caché)" : ""}. El texto pasa un filtro que
                  descarta acusaciones e invenciones antes de mostrarse.
                </>
              ) : (
                <>
                  Texto determinista, sin IA: {res.ai.motivo}. Se usa cuando no hay proveedor
                  disponible o cuando la respuesta del modelo no supera el filtro.
                </>
              )}
            </p>
          )}
        </section>
      )}
    </main>
  );
}
