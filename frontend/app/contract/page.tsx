"use client";
import { useState } from "react";
type Rep = { address: string; is_contract: boolean; verified: boolean; risk_score: number; permissions: string[]; risks: any[]; explanation: string; elapsed_s?: number; code_size_bytes?: number; source_origin?: string; slither_used?: boolean };
export default function ContractPage() {
  const [addr, setAddr] = useState("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48");
  const [res, setRes] = useState<Rep | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const go = async () => {
    setLoading(true); setErr(""); setRes(null);
    try {
      const r = await fetch("http://localhost:8000/analyze-contract", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ address: addr }) });
      if (!r.ok) throw new Error("HTTP " + r.status);
      setRes(await r.json());
    } catch (e: any) { setErr("Fallo. Backend en :8000? " + (e?.message || e)); }
    finally { setLoading(false); }
  };
  const color = res ? (res.risk_score < 30 ? "#16a34a" : res.risk_score < 70 ? "#d97706" : "#dc2626") : "#666";
  return (<main style={{ padding: 28, maxWidth: 860, fontFamily: "system-ui" }}>
    <h1>ChainMind — Smart Contract (Fase 2)</h1>
    <p style={{ color: "#555" }}><a href="/">Wallet</a> · Contrato verificado devuelve permisos peligrosos + score.</p>
    <div style={{ display: "flex", gap: 8 }}>
      <input value={addr} onChange={e => setAddr(e.target.value)} placeholder="0x..." style={{ flex: 1, padding: 10, fontFamily: "monospace" }} />
      <button onClick={go} disabled={loading} style={{ padding: "10px 18px", fontWeight: 700 }}>{loading ? "..." : "Analizar contrato"}</button>
    </div>
    {err && <p style={{ color: "red" }}>{err}</p>}
    {res && (<section style={{ marginTop: 20, border: "1px solid #ddd", borderRadius: 12, padding: 18 }}>
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <img src={"http://localhost:8000/qr/" + res.address} width={96} height={96} alt="QR del contrato" title="Escanear dirección" />
        <code style={{ fontSize: 12 }}>{res.address}</code>
        <span style={{ fontSize: 12, background: res.verified ? "#dcfce7" : "#fee2e2", padding: "2px 8px", borderRadius: 20 }}>{res.verified ? "verificado" : "no verificado"}</span>
        <span style={{ fontSize: 12, color: "#666" }}>{res.code_size_bytes} bytes · {res.source_origin} · slither {res.slither_used ? "sí" : "no"} · {res.elapsed_s}s</span>
      </div>
      <div style={{ marginTop: 12, display: "flex", justifyContent: "space-between" }}><b>Risk score</b><b style={{ color }}>{res.risk_score}/100</b></div>
      <div style={{ background: "#eee", borderRadius: 8, height: 12, marginTop: 6 }}>
        <div style={{ width: res.risk_score + "%", background: color, height: 12, borderRadius: 8 }} />
      </div>
      <h3>Permisos peligrosos</h3>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {res.permissions.length === 0 ? <span style={{ color: "#16a34a" }}>ninguno detectado</span> :
          res.permissions.map(p => <span key={p} style={{ fontSize: 12, background: "#fef2f2", border: "1px solid #fecaca", padding: "3px 8px", borderRadius: 20 }}>{p}</span>)}
      </div>
      <h3>Detalle</h3>
      <ul>{res.risks.map((x: any, i: number) => <li key={i} style={{ fontSize: 13 }}><b>{x.id}</b> (+{x.weight}) [{x.origin}] — {x.message}</li>)}</ul>
      <p style={{ background: "#fffbeb", border: "1px solid #fde68a", borderRadius: 8, padding: 12 }}>{res.explanation}</p>
    </section>)}
  </main>);
}
