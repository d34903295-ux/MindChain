"use client";

import { useState } from "react";
import { Chip, RiskGauge, Skeleton, riskTone } from "../../components/ui";

type Risk = { id: string; weight: number; origin: string; message: string };
type Rep = {
  address: string;
  chain: string;
  is_contract: boolean;
  verified: boolean;
  risk_score: number;
  permissions: string[];
  risks: Risk[];
  explanation: string;
  elapsed_s?: number;
  code_size_bytes?: number;
  source_origin?: string;
  slither_used?: boolean;
};

export default function ContractPage() {
  const [addr, setAddr] = useState("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48");
  const [chain, setChain] = useState("ethereum");
  const [res, setRes] = useState<Rep | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const go = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErr("");
    setRes(null);
    try {
      const r = await fetch("http://localhost:8000/analyze-contract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address: addr.trim(), chain }),
      });
      if (!r.ok) throw new Error(`El backend devolvió ${r.status}`);
      setRes(await r.json());
    } catch (e: unknown) {
      setErr(`Fallo. ¿Backend en :8000? ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main id="contenido" className="container page">
      <header className="page-head">
        <p className="eyebrow">Smart Contract</p>
        <h1 className="page-title">Audita un contrato</h1>
        <p className="section-lede">
          Permisos peligrosos y score de riesgo a partir del bytecode y, si está verificado, del
          código fuente con Slither.
        </p>
      </header>

      <section className="card form-card" aria-label="Formulario de análisis">
        <form onSubmit={go} aria-label="Analizar contrato" aria-busy={loading}>
          <div className="form-row">
            <div className="field" style={{ maxWidth: "12rem" }}>
              <label htmlFor="c-chain">Red</label>
              <select
                id="c-chain"
                className="select"
                value={chain}
                onChange={e => setChain(e.target.value)}
              >
                <option value="ethereum">Ethereum</option>
                <option value="base">Base</option>
              </select>
            </div>
            <div className="field" style={{ flex: "1 1 22rem" }}>
              <label htmlFor="c-addr">Dirección del contrato (0x + 40 hex)</label>
              <input
                id="c-addr"
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
              {loading ? "Analizando…" : "Analizar contrato"}
            </button>
          </div>
          <p className="form-hint">Funciona con cualquier contrato; el código fuente se consulta si está verificado.</p>
        </form>

        {err && (
          <p role="alert" className="error-text">
            {err}
          </p>
        )}
        {loading && <Skeleton label="Analizando contrato" />}
      </section>

      {res && (
        <section aria-live="polite" aria-label="Resultado del contrato" className="card result-enter">
          <div className="result-head">
            <figure className="qr-frame" style={{ margin: 0 }}>
              <img
                src={`http://localhost:8000/qr/${res.address}`}
                width={104}
                height={104}
                alt={`Código QR de la dirección ${res.address}`}
              />
              <figcaption>QR del contrato</figcaption>
            </figure>
            <div className="result-ident">
              <h2 className="mono result-addr">{res.address}</h2>
              <p className="result-meta">
                <span className="chip">{res.chain}</span>
                <span className="chip">{res.code_size_bytes} bytes</span>
                <span className="chip">{res.source_origin}</span>
                <span className="chip">slither {res.slither_used ? "sí" : "no"}</span>
                <span className="chip">{res.elapsed_s}s</span>
              </p>
              <p className="result-actions">
                {res.verified ? <Chip tone="ok">verificado</Chip> : <Chip tone="bad">no verificado</Chip>}
                {!res.is_contract && <Chip tone="warn">no es contrato (EOA)</Chip>}
              </p>
            </div>
          </div>

          <div className="result-risk">
            <RiskGauge value={res.risk_score} label="Riesgo" />
          </div>

          <h3>Permisos peligrosos</h3>
          <div className="chip-row">
            {res.permissions.length === 0 ? (
              <Chip tone="ok">ninguno detectado</Chip>
            ) : (
              res.permissions.map(p => (
                <Chip key={p} tone={riskTone(res.risk_score)}>
                  {p}
                </Chip>
              ))
            )}
          </div>

          <h3>Detalle</h3>
          {res.risks.length === 0 ? (
            <p style={{ color: "var(--muted)" }}>Sin hallazgos.</p>
          ) : (
            <ul className="findings">
              {[...res.risks].sort((a, b) => b.weight - a.weight).map((x, i) => (
                <li key={`${x.id}-${i}`}>
                  <span className="finding-id">{x.id}</span>
                  <span className="finding-weight" data-tone={riskTone(x.weight * 3)}>
                    +{x.weight}
                  </span>
                  <span className="finding-origin">{x.origin}</span>
                  <span className="finding-msg">{x.message}</span>
                </li>
              ))}
            </ul>
          )}

          <h3>Explicación</h3>
          <p className="explainer">{res.explanation}</p>
        </section>
      )}
    </main>
  );
}
