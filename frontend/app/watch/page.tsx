"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Skeleton } from "../../components/ui";

type Tx = {
  hash: string;
  from: string;
  to: string | null;
  block: number | null;
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
  n_new_alerts?: number;
  elapsed_s: number;
  median_eth?: number | null;
  mad_eth?: number | null;
  baseline_samples?: number;
  detectors?: string[];
};

type Sentinel = {
  enabled: boolean;
  cycles: number;
  alerts_delivered: number;
  last_error: string | null;
  telegram_configured: boolean;
};

type Job = { exists: boolean; n_wallets?: number; n_anomalies?: number; generated_at?: string; model?: string };

type Watched = {
  address: string;
  label: string;
  verificado?: boolean | null;
  code_bytes?: number | null;
};

const POLL_MS = 12000;

const FLAG_TEXT: Record<string, string> = {
  creacion_contrato: "crea contrato",
  gas_alto: "gas alto",
  gas_muy_alto: "gas muy alto",
  payload_grande: "payload grande",
  "ballena_100eth+": "ballena 100+ ETH",
  "ballena_1000eth+": "ballena 1.000+ ETH",
};

function flagLabel(flag: string): string {
  if (FLAG_TEXT[flag]) return FLAG_TEXT[flag];
  if (flag.startsWith("outlier_") && flag.includes("mediana")) {
    const ratio = flag.split("_")[1]?.replace(/x$/, "");
    return `${ratio}× la mediana`;
  }
  if (flag.startsWith("outlier_estadistico_z")) return "outlier estadístico";
  if (flag.startsWith("watchlist:")) return `watchlist: ${flag.split(":")[1]}`;
  return flag.replace(/_/g, " ");
}

function short(h: string): string {
  if (h.length < 16) return h;
  return `${h.slice(0, 10)}…${h.slice(-6)}`;
}

export default function WatchPage() {
  const [chain, setChain] = useState("ethereum");
  const [feed, setFeed] = useState<Feed | null>(null);
  const [auto, setAuto] = useState(true);
  const [onlyAlerts, setOnlyAlerts] = useState(false);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [seen, setSeen] = useState(0);
  const [alertTotal, setAlertTotal] = useState(0);
  const sinceRef = useRef<number | null>(null);
  const [sentinel, setSentinel] = useState<Sentinel | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [watchlist, setWatchlist] = useState<Watched[]>([]);
  const [wlAddr, setWlAddr] = useState("");
  const [wlLabel, setWlLabel] = useState("");
  const [wlMsg, setWlMsg] = useState("");

  const loadWatchlist = useCallback(() => {
    fetch("http://localhost:8000/watchlist")
      .then(r => (r.ok ? r.json() : Promise.reject()))
      .then(j => setWatchlist(j.addresses ?? []))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    loadWatchlist();
  }, [loadWatchlist]);

  const loadStatus = useCallback(() => {
    fetch("http://localhost:8000/status")
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((j) => {
        setSentinel(j.sentinel ?? null);
        setJob(j.anomaly_job ?? null);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const load = useCallback(
    async (reset = false) => {
      setLoading(true);
      try {
        const since = reset ? null : sinceRef.current;
        const q = since ? `?since=${since}&max_blocks=3` : `?max_blocks=2`;
        const r = await fetch(`http://localhost:8000/feed/${chain}${q}`);
        if (r.status === 429) {
          // el guard nos frena: no es un fallo, solo hay que esperar
          setBusy(true);
          return;
        }
        if (!r.ok) throw new Error(`El backend devolvió ${r.status}`);
        const j: Feed = await r.json();
        sinceRef.current = j.latest;
        setFeed(j);
        setSeen(s => s + j.n_txs);
        setAlertTotal(s => s + j.n_alerts);
        setErr("");
        setBusy(false);
        loadStatus();
      } catch (e: unknown) {
        setErr(`Sin datos. ¿Backend en :8000? ${e instanceof Error ? e.message : String(e)}`);
      } finally {
        setLoading(false);
      }
    },
    [chain, loadStatus]
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

  const rows = feed ? (onlyAlerts ? feed.txs.filter(t => t.alert) : feed.txs).slice(0, 60) : [];

  return (
    <main id="contenido" className="container page">
      <header className="page-head">
        <p className="eyebrow">Vigilancia 24/7</p>
        <h1 className="page-title">Feed en vivo</h1>
        <p className="section-lede">
          Los agentes Monitoring, Transaction y Risk revisan cada bloque y marcan anomalías sin que
          tengas que pedir nada.
        </p>
      </header>

      <div className="watch-bar">
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
              <select id="w-chain" className="select" value={chain} onChange={e => setChain(e.target.value)}>
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
            <div className="field" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <input
                id="w-alerts"
                type="checkbox"
                checked={onlyAlerts}
                onChange={e => setOnlyAlerts(e.target.checked)}
                style={{ width: "1.25rem", height: "1.25rem" }}
              />
              <label htmlFor="w-alerts">Solo alertas</label>
            </div>
          </div>
        </form>
        <p aria-live="polite" style={{ color: "var(--muted)", fontSize: "0.875rem", margin: "0.5rem 0 0" }}>
          {feed
            ? `Bloque ${feed.latest} · vigiladas ${seen} · alertas ${alertTotal}`
            : "Conectando con la red…"}
          {busy && " · saturado, reintentando…"}
          {feed?.median_eth != null && (
            <>
              {" · "}mediana {feed.median_eth} ETH
              {feed.mad_eth != null && ` · MAD ${feed.mad_eth}`}
              {feed.baseline_samples ? ` · base ${feed.baseline_samples}` : " ·PEC"}
            </>
          )}
        </p>
        {sentinel && (
          <p className="sentinel-line">
            <span className={sentinel.enabled ? "dot live" : "dot off"} aria-hidden="true" />
            Centinela {sentinel.enabled ? "activo" : "apagado"}
            {sentinel.enabled && ` · ${sentinel.cycles} ciclos · ${sentinel.alerts_delivered} entregadas`}
            {!sentinel.telegram_configured && " · Telegram sin configurar"}
            {sentinel.last_error && ` · error: ${sentinel.last_error.slice(0, 60)}`}
          </p>
        )}
        {job?.exists && (
          <p className="sentinel-line">
            Job nocturno ({job.model}): {job.n_wallets} wallets · {job.n_anomalies} anomalías
            {job.generated_at ? ` · ${new Date(job.generated_at).toLocaleString("es")}` : ""}
          </p>
        )}
      </div>

      <section className="card" aria-labelledby="wl-title" style={{ marginTop: "1.5rem" }}>
        <h2 id="wl-title" style={{ margin: 0, fontSize: "1rem" }}>
          Wallets vigiladas
        </h2>
        <p style={{ color: "var(--muted)", fontSize: "0.8125rem", margin: "0.25rem 0 0.75rem" }}>
          Señal de screening, no veredicto. Al añadir se comprueba que el contrato exista on-chain.
        </p>
        <form
          className="wl-form"
          onSubmit={async e => {
            e.preventDefault();
            setWlMsg("");
            const r = await fetch("http://localhost:8000/watchlist", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ address: wlAddr.trim(), label: wlLabel.trim() || "watchlist" }),
            });
            const j = await r.json();
            if (!r.ok) {
              setWlMsg(j.detail || "No se pudo añadir");
              return;
            }
            setWlAddr("");
            setWlLabel("");
            setWlMsg(j.added ? "Añadida y vigilada" : j.reason || "Sin cambios");
            loadWatchlist();
          }}
        >
          <div className="field">
            <label htmlFor="wl-addr">Dirección</label>
            <input
              id="wl-addr"
              className="input mono"
              placeholder="0x…"
              value={wlAddr}
              onChange={e => setWlAddr(e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="wl-label">Etiqueta</label>
            <input
              id="wl-label"
              className="input"
              placeholder="mixer, exchange…"
              value={wlLabel}
              onChange={e => setWlLabel(e.target.value)}
            />
          </div>
          <button type="submit" className="btn btn-secondary" disabled={!wlAddr}>
            Vigilar
          </button>
        </form>
        {wlMsg && (
          <p role="status" style={{ fontSize: "0.8125rem", margin: "0.5rem 0 0" }}>
            {wlMsg}
          </p>
        )}
        {watchlist.length > 0 && (
          <ul className="wl-list">
            {watchlist.map(w => (
              <li key={w.address}>
                <span className="mono">{short(w.address)}</span>{" "}
                <span className="muted">{w.label}</span>
                {w.verificado === true && <span className="tag-ok">contrato</span>}
                {w.verificado === null && <span className="muted">sin verificar</span>}
                <button
                  type="button"
                  className="btn-ghost"
                  aria-label={`Dejar de vigilar ${w.address}`}
                  onClick={async () => {
                    await fetch(`http://localhost:8000/watchlist/${w.address}`, { method: "DELETE" });
                    loadWatchlist();
                  }}
                >
                  quitar
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {err && (
        <p role="alert" className="error-text">
          {err}
        </p>
      )}

      {loading && !feed && <Skeleton label="Cargando transacciones" />}

      {feed && feed.alerts.length > 0 && (
        <section role="status" aria-label="Alertas de agentes" className="alert-box">
          <h2 style={{ margin: 0, fontSize: "1rem" }}>
            Alertas de agentes ({feed.n_alerts} en últimos bloques)
          </h2>
          <ul style={{ margin: "0.5rem 0 0", paddingInlineStart: "1.125rem" }}>
            {feed.alerts.slice(0, 10).map(t => (
              <li key={t.hash} className="mono" style={{ fontSize: "0.8125rem" }}>
                {short(t.hash)} · {t.value_eth} ETH · score {t.score} ·{" "}
                {t.flags.map(flagLabel).join(", ")}
              </li>
            ))}
          </ul>
        </section>
      )}

      {feed && rows.length > 0 && (
        <div className="table-wrap">
          <table className="data">
            <caption style={{ textAlign: "start", fontWeight: 700, paddingBlockEnd: "0.5rem" }}>
              Últimas transacciones analizadas{onlyAlerts ? " (solo alertas)" : ""}
            </caption>
            <thead>
              <tr>
                <th scope="col">Hash</th>
                <th scope="col">De → Para</th>
                <th scope="col" className="num">Bloque</th>
                <th scope="col" className="num">Valor</th>
                <th scope="col" className="num">Gas</th>
                <th scope="col" className="num">Score</th>
                <th scope="col">Agentes</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(t => (
                <tr key={t.hash} style={t.alert ? { background: "var(--bad-bg)" } : undefined}>
                  <td className="mono">{short(t.hash)}</td>
                  <td className="mono" style={{ fontSize: "0.75rem" }}>
                    {short(t.from)} → {t.to ? short(t.to) : "∅ nuevo contrato"}
                  </td>
                  <td className="num">{t.block ?? "—"}</td>
                  <td className="num">{t.value_eth} ETH</td>
                  <td className="num">{t.gas_price_gwei} gwei</td>
                  <td className="num">
                    <strong
                      style={{
                        color: t.score >= 50 ? "var(--bad)" : t.score >= 20 ? "var(--warn)" : "var(--ok)",
                      }}
                    >
                      {t.score}
                    </strong>
                  </td>
                  <td>
                    {t.flags.length === 0 ? (
                      <span style={{ color: "var(--muted)" }}>limpia</span>
                    ) : (
                      t.flags.map(flagLabel).join(", ")
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {feed && rows.length === 0 && (
        <p style={{ color: "var(--muted)" }}>
          {onlyAlerts ? "Sin alertas en este lote." : "Sin bloques nuevos desde la última revisión."}
        </p>
      )}
    </main>
  );
}
