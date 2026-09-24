"use client";
import { useState } from "react";
type Report = { address: string; profile: any; risk_score: number; risk_factors: string[]; explanation: string; elapsed_s?: number; source?: string };
export default function Home() {
  const [addr, setAddr] = useState("0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045");
  const [res, setRes] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const analyze = async () => {
    setLoading(true); setErr(""); setRes(null);
    try {
      const t0 = Date.now();
      const r = await fetch("http://localhost:8000/analyze-wallet", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ address: addr }) });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const j = await r.json();
      j.client_s = (Date.now() - t0) / 1000;
      setRes(j);
    } catch (e: any) { setErr("No se pudo analizar. ¿Backend en :8000? " + (e?.message || e)); }
    finally { setLoading(false); }
  };
  const color = res ? (res.risk_score < 30 ? "#16a34a" : res.risk_score < 70 ? "#d97706" : "#dc2626") : "#666";
  return (<main style={{ padding: 28, maxWidth: 860, fontFamily: "system-ui" }}>
    <h1>ChainMind — Wallet Intelligence (Fase 1 MVP)</h1>
    <p style={{ color: "#555" }}>Pega una dirección Ethereum y obtén perfil + score + explicación en &lt;10s.</p>
    <div style={{ display: "flex", gap: 8 }}>
      <input value={addr} onChange={e => setAddr(e.target.value)} placeholder="0x..." style={{ flex: 1, padding: 10, fontFamily: "monospace" }} />
      <button onClick={analyze} disabled={loading} style={{ padding: "10px 18px", fontWeight: 700 }}>{loading ? "..." : "Analizar"}</button>
    </div>
    {err && <p style={{ color: "red" }}>{err}</p>}
    {res && (<section style={{ marginTop: 20, border: "1px solid #ddd", borderRadius: 12, padding: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <code style={{ fontSize: 12 }}>{res.address}</code>
        <span style={{ fontSize: 12, color: "#666" }}>{res.elapsed_s}s servidor · fuente {res.source}</span>
      </div>
      <div style={{ marginTop: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between" }}><b>Risk score</b><b style={{ color }}>{res.risk_score}/100</b></div>
        <div style={{ background: "#eee", borderRadius: 8, height: 12, marginTop: 6 }}>
          <div style={{ width: res.risk_score + "%", background: color, height: 12, borderRadius: 8 }} />
        </div>
        <div style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
          {res.risk_factors.length === 0 ? <span style={{ fontSize: 13, color: "#16a34a" }}>sin factores de riesgo</span> :
            res.risk_factors.map(f => <span key={f} style={{ fontSize: 12, background: "#fef2f2", border: "1px solid #fecaca", padding: "3px 8px", borderRadius: 20 }}>{f}</span>)}
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))", gap: 10, marginTop: 14 }}>
        {[["Txs lifetime", res.profile.tx_count], ["Antigüedad (días)", res.profile.age_days ?? "—"], ["Actividad", res.profile.activity], ["Frec. tx/día", res.profile.freq_tx_day], ["Balance USD", "$" + Number(res.profile.balance_usd || 0).toLocaleString()], ["Contrapartes (muestra)", res.profile.counterparties_sample], ["Bot-like", String(res.profile.bot_like)], ["Labels", (res.profile.labels || []).join(", ")]].map(([k, v]: any) => (
          <div key={k} style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: 10 }}>
            <div style={{ fontSize: 11, color: "#64748b" }}>{k}</div><div style={{ fontWeight: 700 }}>{String(v)}</div>
          </div>))}
      </div>
      <h3>Explicación</h3>
      <p style={{ background: "#fffbeb", border: "1px solid #fde68a", borderRadius: 8, padding: 12 }}>{res.explanation}</p>
    </section>)}
  </main>);
}
