"use client";
import { useCallback, useEffect, useRef, useState } from "react";

type Tx = {
  hash: string; from: string; to: string | null; value_eth: number;
  gas_price_gwei: number; score: number; flags: string[]; alert: boolean;
};
type Feed = {
  chain: string; latest: number; blocks: { number: number; tx_count: number }[];
  txs: Tx[]; alerts: Tx[]; n_txs: number; n_alerts: number; elapsed_s: number;
};

const POLL_MS = 12000;

export default function WatchPage() {
  const [chain, setChain] = useState("ethereum");
  const [feed, setFeed] = useState<Feed | null>(null);
  const [auto, setAuto] = useState(true);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [seen, setSeen] = useState(0);
  const [alertTotal, setAlertTotal] = useState(0);
  const sinceRef = useRef<number | null>(null);

  const load = useCallback(async (reset = false) => {
    setLoading(true);
    try {
      const since = reset ? null : sinceRef.current;
      const q = since ? `?since=${since}&max_blocks=3` : `?max_blocks=2`;
      const r = await fetch(`http://localhost:8000/feed/${chain}${q}`);
      if (!r.ok) throw new Error("HTTP " + r.status);
      const j: Feed = await r.json();
      sinceRef.current = j.latest;
      setFeed(j);
      setSeen(s => s + j.n_txs);
      setAlertTotal(s => s + j.n_alerts);
      setErr("");
    } catch (e: unknown) {
      setErr("Sin datos. ¿Backend en :8000? " + (e instanceof Error ? e.message : String(e)));
    } finally {
      setLoading(false);
    }
  }, [chain]);

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

  const short = (h: string) => h.slice(0, 10) + "…" + h.slice(-6);

  return (
    <main style={{ padding: 28, maxWidth: 1100, fontFamily: "system-ui" }}>
      <h1>ChainMind — Vigilancia en vivo</h1>
      <p style={{ color: "#555" }}>
        <a href="/">Wallet</a> · <a href="/contract">Contrato</a> · Los agentes vigilan cada transacción de la red y marcan anomalías solos.
      </p>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <select value={chain} onChange={e => setChain(e.target.value)} style={{ padding: 10 }}>
          <option value="ethereum">Ethereum</option>
          <option value="base">Base</option>
        </select>
        <button onClick={() => load(false)} disabled={loading} style={{ padding: "10px 18px", fontWeight: 700 }}>
          {loading ? "…" : "Actualizar"}
        </button>
        <label style={{ fontSize: 14 }}>
          <input type="checkbox" checked={auto} onChange={e => setAuto(e.target.checked)} /> auto (12s)
        </label>
        {feed && (
          <span style={{ fontSize: 13, color: "#555" }}>
            bloque {feed.latest} · vigiladas {seen} · <b style={{ color: alertTotal ? "#dc2626" : "#16a34a" }}>alertas {alertTotal}</b>
          </span>
        )}
      </div>
      {err && <p style={{ color: "red" }}>{err}</p>}
      {feed && feed.alerts.length > 0 && (
        <section style={{ marginTop: 16, border: "2px solid #fecaca", background: "#fef2f2", borderRadius: 12, padding: 14 }}>
          <b>Alertas de agentes ({feed.n_alerts} en últimos bloques)</b>
          <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
            {feed.alerts.slice(0, 10).map(t => (
              <li key={t.hash} style={{ fontSize: 13, fontFamily: "monospace" }}>
                {short(t.hash)} · {t.value_eth} ETH · score {t.score} · {t.flags.join(", ")}
              </li>
            ))}
          </ul>
        </section>
      )}
      {feed && (
        <table style={{ marginTop: 16, width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "2px solid #ddd" }}>
              <th>Hash</th><th>De → Para</th><th>Valor</th><th>Gas</th><th>Score</th><th>Agentes</th>
            </tr>
          </thead>
          <tbody>
            {feed.txs.slice(0, 60).map(t => (
              <tr key={t.hash} style={{ borderBottom: "1px solid #eee", background: t.alert ? "#fef2f2" : "transparent" }}>
                <td style={{ fontFamily: "monospace" }}>{short(t.hash)}</td>
                <td style={{ fontFamily: "monospace", fontSize: 12 }}>{short(t.from)} → {t.to ? short(t.to) : "∅ nuevo contrato"}</td>
                <td>{t.value_eth} ETH</td>
                <td>{t.gas_price_gwei} gwei</td>
                <td><b style={{ color: t.score >= 50 ? "#dc2626" : t.score >= 20 ? "#d97706" : "#16a34a" }}>{t.score}</b></td>
                <td>{t.flags.length === 0 ? <span style={{ color: "#999" }}>limpia</span> : t.flags.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {feed && feed.txs.length === 0 && <p style={{ color: "#555" }}>Sin bloques nuevos desde la última revisión.</p>}
    </main>
  );
}
