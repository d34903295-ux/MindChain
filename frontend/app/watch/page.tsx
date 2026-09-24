"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type Tx = {
  hash: string;
  from: string;
  to: string | null;
  value_eth: number;
  gas_price_gwei: number;
  score: number;
  flags: string[];
  alert: boolean;
};
type Feed = {
  chain: string;
  latest: number;
  blocks: { number: number; tx_count: number }[];
  txs: Tx[];
  alerts: Tx[];
  n_txs: number;
  n_alerts: number;
  elapsed_s: number;
};

const POLL_MS = 12000;

function short(h: string): string {
  if (h.length < 16) return h;
  return `${h.slice(0, 10)}…${h.slice(-6)}`;
}

export default function WatchPage() {
  const [chain, setChain] = useState("ethereum");
  const [feed, setFeed] = useState<Feed | null>(null);
  const [auto, setAuto] = useState(true);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [seen, setSeen] = useState(0);
  const [alertTotal, setAlertTotal] = useState(0);
  const sinceRef = useRef<number | null>(null);

  const load = useCallback(
    async (reset = false) => {
      setLoading(true);
      try {
        const since = reset ? null : sinceRef.current;
        const q = since ? `?since=${since}&max_blocks=3` : `?max_blocks=2`;
        const r = await fetch(`http://localhost:8000/feed/${chain}${q}`);
        if (!r.ok) throw new Error(`El backend devolvió ${r.status}`);
        const j: Feed = await r.json();
        sinceRef.current = j.latest;
        setFeed(j);
        setSeen(s => s + j.n_txs);
        setAlertTotal(s => s + j.n_alerts);
        setErr("");
      } catch (e: unknown) {
        setErr(`Sin datos. ¿Backend en :8000? ${e instanceof Error ? e.message : String(e)}`);
      } finally {
        setLoading(false);
      }
    },
    [chain]
  );

  useEffect(() => {
    sinceRef.current = null;
    setSeen(0);
    setAlertTotal(0);
    setFeed(null);
    load(true);
  }, [chain, load]);

  useEffect(() => {
    if (!auto) return;
    const id = setInterval(() => load(false), POLL_MS);
    return () => clearInterval(id);
  }, [auto, load]);

  return (
    <main id="contenido" className="container" style={{ paddingBlock: "1.5rem" }}>
      <h1>Vigilancia en vivo</h1>
      <p style={{ color: "var(--muted)" }}>
        Los agentes vigilan cada transacción de la red y marcan anomalías solos.
      </p>

      <form
        aria-label="Opciones de vigilancia"
        onSubmit={e => {
          e.preventDefault();
          load(false);
        }}
      >
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "end", flexWrap: "wrap" }}>
          <div className="field" style={{ minWidth: "10rem" }}>
            <label htmlFor="w-chain">Red</label>
            <select
              id="w-chain"
              className="select"
              value={chain}
              onChange={e => setChain(e.target.value)}
            >
              <option value="ethereum">Ethereum</option>
              <option value="base">Base</option>
            </select>
          </div>
          <button type="submit" className="btn btn-secondary" disabled={loading}>
            {loading ? "Actualizando…" : "Actualizar"}
          </button>
          <div className="field" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <input
              id="w-auto"
              type="checkbox"
              checked={auto}
              onChange={e => setAuto(e.target.checked)}
              style={{ width: "1.25rem", height: "1.25rem" }}
            />
            <label htmlFor="w-auto">Automático (12s)</label>
          </div>
        </div>
      </form>

      {err && (
        <p role="alert" className="error-text">
          {err}
        </p>
      )}

      <p aria-live="polite" style={{ color: "var(--muted)", fontSize: "0.875rem" }}>
        {feed
          ? `Bloque ${feed.latest} · vigiladas ${seen} · alertas ${alertTotal}`
          : "Conectando con la red…"}
      </p>

      {feed && feed.alerts.length > 0 && (
        <section role="status" aria-label="Alertas de agentes" className="alert-box">
          <h2 style={{ margin: 0, fontSize: "1rem" }}>
            Alertas de agentes ({feed.n_alerts} en últimos bloques)
          </h2>
          <ul style={{ margin: "0.5rem 0 0", paddingInlineStart: "1.125rem" }}>
            {feed.alerts.slice(0, 10).map(t => (
              <li key={t.hash} className="mono" style={{ fontSize: "0.8125rem" }}>
                {short(t.hash)} · {t.value_eth} ETH · score {t.score} · {t.flags.join(", ")}
              </li>
            ))}
          </ul>
        </section>
      )}

      {feed && feed.txs.length > 0 && (
        <div className="table-wrap">
          <table className="data">
            <caption style={{ textAlign: "start", fontWeight: 700, paddingBlockEnd: "0.5rem" }}>
              Últimas transacciones analizadas
            </caption>
            <thead>
              <tr>
                <th scope="col">Hash</th>
                <th scope="col">De → Para</th>
                <th scope="col" className="num">
                  Valor
                </th>
                <th scope="col" className="num">
                  Gas
                </th>
                <th scope="col" className="num">
                  Score
                </th>
                <th scope="col">Agentes</th>
              </tr>
            </thead>
            <tbody>
              {feed.txs.slice(0, 60).map(t => (
                <tr key={t.hash} style={t.alert ? { background: "var(--bad-bg)" } : undefined}>
                  <td className="mono">{short(t.hash)}</td>
                  <td className="mono" style={{ fontSize: "0.75rem" }}>
                    {short(t.from)} → {t.to ? short(t.to) : "∅ nuevo contrato"}
                  </td>
                  <td className="num">{t.value_eth} ETH</td>
                  <td className="num">{t.gas_price_gwei} gwei</td>
                  <td className="num">
                    <strong
                      style={{
                        color:
                          t.score >= 50
                            ? "var(--bad)"
                            : t.score >= 20
                              ? "var(--warn)"
                              : "var(--ok)",
                      }}
                    >
                      {t.score}
                    </strong>
                  </td>
                  <td>{t.flags.length === 0 ? <span style={{ color: "var(--muted)" }}>limpia</span> : t.flags.join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {feed && feed.txs.length === 0 && (
        <p style={{ color: "var(--muted)" }}>Sin bloques nuevos desde la última revisión.</p>
      )}
    </main>
  );
}
