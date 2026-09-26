"use client";

import { API_BASE } from "../lib/api";
import { useCallback, useEffect, useState } from "react";

type Status = {
  configured: boolean;
  vault_detected: string | null;
  exists: boolean;
  auto_export: boolean;
};

type Props = {
  address: string;
  chain: string;
  kind: "wallet" | "contract";
  /** Si viene del análisis ya hecho, se reutiliza en vez de recalcular. */
  riskScore?: number | null;
};

export function ObsidianExport({ address, chain, kind, riskScore }: Props) {
  const [st, setSt] = useState<Status | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [ok, setOk] = useState(false);

  useEffect(() => {
    fetch("${API_BASE}/obsidian/status")
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setSt)
      .catch(() => setSt(null));
  }, []);

  const sync = useCallback(async () => {
    setBusy(true);
    setMsg("");
    try {
      const endpoint = kind === "wallet" ? "/obsidian/sync/wallet" : "/obsidian/sync/contract";
      const r = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address, chain }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`);
      setOk(Boolean(j.written));
      setMsg(j.written ? "Guardada en tu vault" : "Sin cambios que guardar");
    } catch (e: unknown) {
      setOk(false);
      setMsg(e instanceof Error ? e.message : "No se pudo exportar");
    } finally {
      setBusy(false);
    }
  }, [address, chain, kind]);

  if (!st) return null;

  return (
    <div className="obsidian-row">
      <button type="button" className="copy-btn" onClick={sync} disabled={busy} aria-label="Exportar a Obsidian">
        {busy ? "Guardando…" : "Exportar a Obsidian"}
      </button>
      {riskScore !== undefined && <span className="obsidian-score">score {riskScore ?? "n/d"}</span>}
      {msg && (
        <span className="obsidian-msg" data-ok={ok} aria-live="polite">
          {msg}
        </span>
      )}
      {!st.auto_export && st.exists && (
        <span className="obsidian-hint" title="Configura CHAINMIND_OBSIDIAN_AUTO=1 para exportar en cada análisis">
          auto-export off
        </span>
      )}
    </div>
  );
}
