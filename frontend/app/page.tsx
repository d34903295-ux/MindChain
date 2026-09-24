"use client";
import { useState } from "react";
export default function Home() {
  const [addr, setAddr] = useState("");
  const [res, setRes] = useState<any>(null);
  const analyze = async () => {
    const r = await fetch("http://localhost:8000/analyze-wallet", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({address: addr})});
    setRes(await r.json());
  };
  return (<main style={{padding:32, maxWidth:720}}>
    <h1>ChainMind — Wallet Intelligence (Fase 0/1)</h1>
    <input value={addr} onChange={e=>setAddr(e.target.value)} placeholder="0x..." style={{width:"100%", padding:8}} />
    <button onClick={analyze} style={{marginTop:8, padding:"8px 16px"}}>Analizar</button>
    {res && <pre style={{marginTop:16, background:"#111", color:"#0f0", padding:16}}>{JSON.stringify(res,null,2)}</pre>}
  </main>);
}
