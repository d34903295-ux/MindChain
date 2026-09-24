"use client";

import { useState } from "react";
import { Chip, ScoreBar, riskTone } from "../../components/ui";

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
    <main id="contenido" className="container" style={{ paddingBlock: "1.5rem" }}>
      <h1>Smart Contract</h1>
      <p style={{ color: "var(--muted)" }}>
        Dado un contrato verificado, devuelve permisos peligrosos y score de riesgo.
      </p>

      <form onSubmit={go} aria-label="Analizar contrato">
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
        <div className="field" style={{ marginBlockStart: "0.75rem" }}>
          <label htmlFor="c-addr">Dirección del contrato (0x + 40 caracteres hex)</label>
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
        <button type="submit" className="btn" disabled={loading} style={{ marginBlockStart: "0.75rem" }}>
          {loading ? "Analizando…" : "Analizar contrato"}
        </button>
      </form>

      {err && (
        <p role="alert" className="error-text">
          {err}
        </p>
      )}

      {res && (
        <section aria-live="polite" aria-label="Resultado del contrato" className="card">
          <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
            <img
              src={`http://localhost:8000/qr/${res.address}`}
              width={96}
              height={96}
              alt={`Código QR de la dirección ${res.address}`}
            />
            <div>
              <h2 className="mono" style={{ fontSize: "1rem", margin: 0 }}>
                {res.address}
              </h2>
              <p style={{ color: "var(--muted)", fontSize: "0.875rem", margin: 0 }}>
                {res.chain} · {res.code_size_bytes} bytes · {res.source_origin} · slither{" "}
                {res.slither_used ? "sí" : "no"} · {res.elapsed_s}s
              </p>
              <p style={{ margin: "0.25rem 0 0" }}>
                {res.verified ? (
                  <Chip tone="ok">verificado</Chip>
                ) : (
                  <Chip tone="bad">no verificado</Chip>
                )}{" "}
                {!res.is_contract && <Chip tone="warn">no es contrato (EOA)</Chip>}
              </p>
            </div>
          </div>

          <div style={{ marginBlockStart: "1rem" }}>
            <ScoreBar value={res.risk_score} label="Riesgo" />
          </div>

          <h3>Permisos peligrosos</h3>
          <div style={{ display: "flex", gap: "0.375rem", flexWrap: "wrap" }}>
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
            <ul>
              {[...res.risks].sort((a, b) => b.weight - a.weight).map((x, i) => (
                <li key={`${x.id}-${i}`} style={{ fontSize: "0.875rem" }}>
                  <strong>{x.id}</strong> (+{x.weight}) [{x.origin}] — {x.message}
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
