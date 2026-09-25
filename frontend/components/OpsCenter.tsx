"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import { AgentPixel } from "./AgentPixel";
import { AgentStation, ScoreDial, Sparkline, type StationData } from "./AgentStation";
import { AgentFloor } from "./AgentFloor";

/**
 * Sala de operaciones de ChainMind.
 *
 * Idea: no es una ilustración de una oficina, es el estado real del sistema.
 * Si el centinela está caído, aquí se ve caído. Si no hay alertas, se ve que no
 * hay alertas. Todo lo que se mueve se mueve porque hay algo detrás.
 *
 * Distribución: núcleo de grafo al centro, una estación por agente alrededor,
 * rieles de métricas a los lados y una banda de eventos abajo. La densidad es
 * alta a propósito (es una sala de control, no una landing), pero el aire se
 * conserva con jerarquía tipográfica y sombras suaves en vez de cajas duras.
 */

type Tx = {
  hash: string;
  from: string;
  to: string | null;
  value_eth: number;
  score: number;
  flags: string[];
  alert: boolean;
  block?: number;
};

type Feed = {
  chain: string;
  latest: number;
  n_txs: number;
  n_alerts: number;
  txs: Tx[];
  median_eth?: number | null;
  mad_eth?: number | null;
  baseline_samples?: number;
};

type Status = {
  ok?: boolean;
  guard?: { in_flight?: Record<string, number>; max_concurrency?: number };
  ia?: {
    provider?: string;
    model?: string;
    local?: boolean;
    estadisticas?: { calls?: number; ok?: number; errors?: number; rejected?: number; cached?: number; usd?: number };
  };
  agentes?: { nombre: string; rol: string; modelo: string }[];
  sentinel?: {
    enabled?: boolean;
    cycles?: number;
    alerts_delivered?: number;
    last_error?: string | null;
    telegram_configured?: boolean;
    last_block?: Record<string, number>;
  };
  watchlist?: { size?: number };
  anomaly_job?: { exists?: boolean; n_wallets?: number; n_anomalies?: number; generated_at?: string };
};

const AGENTE_COLOR: Record<string, string> = {
  wallet: "#1d4ed8",
  transaction: "#b45309",
  contract: "#7c3aed",
  research: "#0891b2",
  monitoring: "#dc2626",
  risk: "#db2777",
  explanation: "#0d9488",
};

const short = (h: string, n = 6) => (h.length > n + 2 ? `${h.slice(0, n)}…${h.slice(-4)}` : h);

function iso(seg: number) {
  const d = Math.floor(seg / 60);
  const s = seg % 60;
  if (d < 60) return `${d}m ${String(s).padStart(2, "0")}s`;
  return `${Math.floor(d / 60)}h ${d % 60}m`;
}

export function OpsCenter() {
  const [feed, setFeed] = useState<Feed | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [cadena, setCadena] = useState<"ethereum" | "base">("ethereum");
  const [reloj, setReloj] = useState("--:--:--");
  const [eventos, setEventos] = useState<{ t: string; txt: string; tipo: "ok" | "alerta" | "info" }[]>([]);
  const [historial, setHistorial] = useState<number[]>(() => Array(28).fill(0));
  const [acumulado, setAcumulado] = useState({ wallets: 0, alertas: 0, tx: 0, bloques: 0 });
  const suave = useReducedMotion();
  const arranque = useRef(Date.now());
  const vistos = useRef<Set<string>>(new Set());
  const walletsVistas = useRef<Set<string>>(new Set());

  // reloj de sala
  useEffect(() => {
    const p = (n: number) => String(n).padStart(2, "0");
    const tick = () => {
      const d = new Date();
      setReloj(`${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  // feed: 6 s. Con el guard de concurrencia y su dedupe, no satura la API.
  useEffect(() => {
    let vivo = true;
    const pedir = () => {
      fetch(`http://localhost:8000/feed/${cadena}?max_blocks=1`)
        .then(r => (r.ok ? r.json() : Promise.reject()))
        .then((j: Feed) => {
          if (!vivo) return;
          setFeed(j);
          setHistorial(h => [...h.slice(1), j.n_txs]);
          // contadores honestos: wallets y alertas se cuentan de lo que ha
          // pasado por la sesión, no se inventan para llenar la casilla
          const nuevos = new Set(walletsVistas.current);
          let nuevosWallets = 0;
          for (const t of j.txs ?? []) {
            for (const a of [t.from, t.to]) {
              if (a && !nuevos.has(a)) {
                nuevos.add(a);
                nuevosWallets += 1;
              }
            }
          }
          walletsVistas.current = nuevos;
          setAcumulado(a => ({
            ...a,
            tx: a.tx + (j.n_txs || 0),
            alertas: a.alertas + (j.n_alerts || 0),
            bloques: a.bloques + 1,
            wallets: a.wallets + nuevosWallets,
          }));
        })
        .catch(() => undefined);
    };
    pedir();
    const id = setInterval(pedir, 6000);
    return () => {
      vivo = false;
      clearInterval(id);
    };
  }, [cadena]);

  // estado del sistema: 9 s
  useEffect(() => {
    let vivo = true;
    const pedir = () => {
      fetch("http://localhost:8000/status")
        .then(r => (r.ok ? r.json() : Promise.reject()))
        .then((j: Status) => vivo && setStatus(j))
        .catch(() => undefined);
    };
    pedir();
    const id = setInterval(pedir, 9000);
    return () => {
      vivo = false;
      clearInterval(id);
    };
  }, []);

  // banda de eventos: lo que acaba de ocurrir, no un log estático
  useEffect(() => {
    if (!feed) return;
    const nuevos: typeof eventos = [];
    for (const t of feed.txs.slice(0, 4)) {
      if (vistos.current.has(t.hash)) continue;
      vistos.current.add(t.hash);
      if (vistos.current.size > 120) vistos.current = new Set([t.hash]);
      nuevos.push({
        t: reloj,
        txt: t.alert
          ? `Alerta ${short(t.hash)} · ${t.value_eth} ETH · score ${t.score}`
          : `${short(t.hash)} · ${t.value_eth} ETH · ${t.flags[0] ?? "transferencia"}`,
        tipo: t.alert ? "alerta" : "info",
      });
    }
    if (feed.n_alerts > 0 && feed.txs[0] && vistos.current.size % 7 === 0) {
      nuevos.push({ t: reloj, txt: `Feed ${cadena}: ${feed.n_alerts} alertas en el bloque ${feed.latest}`, tipo: "alerta" });
    }
    if (nuevos.length) setEventos(e => [...nuevos.reverse(), ...e].slice(0, 14));
  }, [feed, reloj, cadena]);

  const ia = status?.ia;
  const sen = status?.sentinel;
  const riesgo = useMemo(() => (feed?.txs ?? []).reduce((m, t) => Math.max(m, t.score), 0) || null, [feed]);
  const uptime = Math.floor((Date.now() - arranque.current) / 1000);

  // Cada estación se construye con datos reales; si no hay, su texto lo dice.
  const estaciones: Record<string, StationData> = {
    wallet: {
      titulo: "Wallet Agent",
      estado: feed ? `perfilando · bloque ${feed.latest}` : "esperando feed",
      progreso: feed ? Math.min(1, 0.3 + (feed.n_txs || 0) / 90) : null,
      metricas: [
        ["dirs vistas", String(acumulado.wallets)],
        ["bloques", String(acumulado.bloques)],
        ["score top", riesgo === null ? "n/d" : String(riesgo)],
      ],
      lineas: feed?.txs.slice(0, 2).map(t => `${short(t.from, 8)} → ${short(t.to || "contrato nuevo", 8)}`) ?? [],
    },
    transaction: {
      titulo: "Transaction Agent",
      estado: feed ? "leyendo movimientos" : "sin movimientos",
      progreso: feed ? Math.min(1, 0.25 + (feed.n_txs || 0) / 70) : null,
      metricas: [
        ["en bloque", String(feed?.n_txs ?? 0)],
        ["mediana", feed?.median_eth != null ? `${feed.median_eth}` : "n/d"],
        ["total", String(acumulado.tx)],
      ],
      lineas: (feed?.txs ?? []).slice(0, 2).map(t => `${t.value_eth} ETH · ${t.flags[0] ?? "sin señal"}`),
    },
    contract: {
      titulo: "Contract Agent",
      estado: "bytecode y permisos",
      // sin telemetría propia del agente: barra indeterminada, no un % inventado
      progreso: null,
      metricas: [
        ["fuente", "sourcify"],
        ["slither", "opcional"],
        ["wl", String(status?.watchlist?.size ?? 0)],
      ],
      lineas: ["esperando una dirección de contrato", "bytecode y permisos al llegar una"],
    },
    research: {
      titulo: "Research Agent",
      estado: "contexto y screening",
      progreso: null,
      metricas: [
        ["vigiladas", String(status?.watchlist?.size ?? 0)],
        ["job ML", String(status?.anomaly_job?.n_anomalies ?? "—")],
        ["agentes", String(status?.agentes?.length ?? 7)],
      ],
      lineas: [
        "señales de screening: interacción > título",
        `job nocturno: ${status?.anomaly_job?.n_wallets ?? 0} wallets analizadas`,
      ],
    },
    monitoring: {
      titulo: "Monitoring Agent",
      estado: sen?.enabled ? `centinela · ${sen.cycles ?? 0} ciclos` : "centinela apagado",
      progreso: sen?.enabled ? Math.min(1, 0.5 + (sen.cycles ?? 0) / 40) : 0.15,
      alerta: (feed?.n_alerts ?? 0) > 0,
      metricas: [
        ["eventos", String(acumulado.tx)],
        ["alertas", String(sen?.alerts_delivered ?? 0)],
        ["tg", sen?.telegram_configured ? "on" : "off"],
      ],
      lineas: [
        ...(feed?.n_alerts ? [`${feed.n_alerts} señales en el bloque ${feed.latest}`] : ["sin señales en este bloque"]),
        sen?.last_error ? `error: ${sen.last_error.slice(0, 40)}` : "baseline de la red estable",
      ],
    },
    risk: {
      titulo: "Risk Agent",
      estado: "puntaje heurístico",
      progreso: riesgo === null ? null : Math.min(1, 0.2 + riesgo / 120),
      alerta: riesgo !== null && riesgo >= 70,
      metricas: [
        ["score", riesgo === null ? "n/d" : `${riesgo}/100`],
        ["nivel", riesgo === null ? "n/d" : riesgo >= 70 ? "alto" : riesgo >= 30 ? "medio" : "bajo"],
        ["wl", String(status?.watchlist?.size ?? 0)],
      ],
      lineas: [`mediana de red ${feed?.median_eth ?? "n/d"} ETH`, `MAD ${feed?.mad_eth ?? "n/d"}`],
    },
    explanation: {
      titulo: "Explanation Agent",
      estado: ia?.provider ? `redactando con ${ia.model}` : "texto determinista",
      progreso: ia?.estadisticas ? Math.min(1, 0.3 + (ia.estadisticas.ok ?? 0) / 25) : null,
      metricas: [
        ["hechos", String(ia?.estadisticas?.ok ?? 0)],
        ["vetados", String(ia?.estadisticas?.rejected ?? 0)],
        ["coste", `$${(ia?.estadisticas?.usd ?? 0).toFixed(3)}`],
      ],
      lineas: ia?.local
        ? ["IA local: ningún dato sale de la máquina", `caché: ${ia?.estadisticas?.cached ?? 0} respuestas`]
        : ["sin proveedor: se usa texto determinista", "configura ANTHROPIC_API_KEY para narrar"],
    },
  };

  const orden = ["wallet", "transaction", "contract", "research", "monitoring", "risk", "explanation"] as const;

  // lo que cada robot hace en la planta: su carga y su alarma son las mismas
  // que ya mostraba cada estación, no un adorno nuevo
  const cargas = Object.fromEntries(
    orden.map(id => [id, estaciones[id].progreso ?? 0.4]),
  ) as Record<string, number>;
  const alarmas = Object.fromEntries(
    orden.map(id => [id, estaciones[id].alerta === true]),
  ) as Record<string, boolean>;

  return (
    <div className="ops2">
      {/* ---------- cabecera ---------- */}
      <header className="ops2-head">
        <div className="ops2-head-l">
          <span className={status?.ok ? "pill is-ok" : "pill"}>
            <span className="pill-dot" aria-hidden="true" />
            {status?.ok ? "Sistema online" : "conectando"}
          </span>
          <span className="pill">
            {status?.agentes?.length ?? 7} agentes activos
          </span>
          <span className="pill">
            {ia?.provider ? `IA ${ia.provider}${ia.model ? ` · ${ia.model}` : ""}` : "IA no configurada"}
          </span>
        </div>
        <div className="ops2-head-r">
          <div className="chain-toggle" role="group" aria-label="Red vigilada">
            {(["ethereum", "base"] as const).map(c => (
              <button
                key={c}
                type="button"
                className={cadena === c ? "is-on" : ""}
                onClick={() => setCadena(c)}
                aria-pressed={cadena === c}
              >
                {c === "ethereum" ? "Ethereum" : "Base"}
              </button>
            ))}
          </div>
          <span className="ops2-clock mono">{reloj}</span>
          <span className={sen?.enabled ? "pill-dot is-live" : "pill-dot"} aria-label="centinela" />
        </div>
      </header>

      <div className="ops2-grid">
        {/* ---------- riel izquierdo ---------- */}
        <aside className="rail rail-l" aria-label="Actividad del sistema">
          <Panel titulo="Actividad en tiempo real" badge={feed ? `bloque ${feed.latest}` : "conectando"}>
            <div className="kpi-grid">
              <Kpi etiqueta="Transacciones" valor={String(feed?.n_txs ?? 0)} delta={`${historial[historial.length - 1] ?? 0} en bloque`} />
              <Kpi etiqueta="Alertas" valor={String(feed?.n_alerts ?? 0)} alerta={(feed?.n_alerts ?? 0) > 0} delta="heurística" />
              <Kpi etiqueta="Direcciones vistas" valor={String(acumulado.wallets)} delta={`${acumulado.bloques} bloques`} />
              <Kpi etiqueta="IA · llamadas" valor={String(ia?.estadisticas?.calls ?? 0)} delta={`${ia?.estadisticas?.rejected ?? 0} descartadas`} />
            </div>
            <Sparkline valores={historial} color={AGENTE_COLOR.wallet} alto={40} />
          </Panel>

          <Panel titulo="Redes vigiladas">
            <ul className="net-list">
              {(["ethereum", "base"] as const).map(c => {
                const bloq = sen?.last_block?.[c];
                return (
                  <li key={c}>
                    <span className="net-name">
                      <span className={cadena === c ? "net-dot is-on" : "net-dot"} aria-hidden="true" />
                      {c === "ethereum" ? "Ethereum" : "Base"}
                    </span>
                    <span className="net-block mono">{bloq ? `#${bloq.toLocaleString("es")}` : "—"}</span>
                  </li>
                );
              })}
            </ul>
            <div className="net-foot">
              <span>guard {status?.guard?.max_concurrency ?? 2} slots</span>
              <span>dedupe {status?.guard?.in_flight?.["feed:ethereum"] ?? 0} en vuelo</span>
            </div>
          </Panel>

          <Panel titulo="Alertas recientes" alerta={(feed?.n_alerts ?? 0) > 0}>
            {(feed?.txs ?? []).filter(t => t.alert).length === 0 && feed?.n_alerts === 0 ? (
              <p className="empty">Sin alertas. El baseline de la red está estable.</p>
            ) : (
              <ul className="alert-list">
                {(feed?.txs ?? []).slice(0, 3).map(t => (
                  <li key={t.hash}>
                    <span className="alert-dot" aria-hidden="true" />
                    <span className="alert-txt">
                      {t.value_eth} ETH
                      <small className="mono"> {short(t.hash)}</small>
                    </span>
                    <span className="alert-score mono">{t.score}</span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel titulo="Distribución de score" badge={cadena}>
            {(() => {
              const cubos = [0, 0, 0, 0, 0];
              for (const t of feed?.txs ?? []) cubos[Math.min(4, Math.floor(t.score / 20))] += 1;
              const tope = Math.max(1, ...cubos);
              const etiquetas = ["0-19", "20-39", "40-59", "60-79", "80+"];
              return (
                <ul className="dist-list">
                  {cubos.map((c, i) => (
                    <li key={etiquetas[i]}>
                      <span className="dist-label mono">{etiquetas[i]}</span>
                      <span className="dist-bar">
                        <motion.span
                          className={i >= 3 ? "fill is-hot" : i === 2 ? "fill is-warm" : "fill"}
                          animate={{ width: `${(c / tope) * 100}%` }}
                          transition={{ duration: 0.6, ease: "easeOut" }}
                        />
                      </span>
                      <span className="dist-n mono">{c}</span>
                    </li>
                  ))}
                </ul>
              );
            })()}
          </Panel>

          <Panel titulo="Direcciones por valor" badge="top 5">
            {(feed?.txs ?? []).length === 0 ? (
              <p className="empty">Sin movimientos en este bloque.</p>
            ) : (
              <ul className="top-list">
                {[...(feed?.txs ?? [])]
                  .sort((a, b) => b.value_eth - a.value_eth)
                  .slice(0, 5)
                  .map(t => (
                    <li key={t.hash}>
                      <span className="top-addr mono">{short(t.from, 7)}</span>
                      <span className="top-bar" aria-hidden="true">
                        <span style={{ width: `${Math.min(100, (t.value_eth / Math.max(1, riesgo ?? 100)) * 100)}%` }} />
                      </span>
                      <span className="top-val mono">{t.value_eth}</span>
                    </li>
                  ))}
              </ul>
            )}
          </Panel>
        </aside>

        {/* ---------- centro: núcleo rodeado por los 7 agentes (rejilla 3x3) ---------- */}
        <main className="ops2-center">
          <div className="ops2-stage">
            <div className="stage-slot s-research"><AgentStation id="research" color={AGENTE_COLOR.research} data={estaciones.research} /></div>
            <div className="stage-slot s-wallet"><AgentStation id="wallet" color={AGENTE_COLOR.wallet} data={estaciones.wallet} /></div>
            <div className="stage-slot s-contract"><AgentStation id="contract" color={AGENTE_COLOR.contract} data={estaciones.contract} /></div>

            <div className="stage-slot s-core">
              <div className="core-wrap">
                <div className="core-halo" aria-hidden="true" />
                <AgentFloor
                  txs={feed?.txs ?? []}
                  cadena={cadena}
                  carga={cargas}
                  alerta={alarmas}
                />
                <div className="core-foot">
                  <ul className="core-legend">
                    <li><span className="cl cl-wallet" /> wallets</li>
                    <li><span className="cl cl-ctr" /> contratos</li>
                    <li><span className="cl cl-net" /> red</li>
                    <li><span className="cl cl-alert" /> alerta</li>
                  </ul>
                  <p className="core-caption">
                    <strong className="mono">#{feed?.latest?.toLocaleString("es") ?? "—"}</strong>
                    <span>{cadena}</span>
                    <span className="core-live"><span aria-hidden="true" /> en vivo</span>
                  </p>
                </div>
              </div>
            </div>

            <div className="stage-slot s-risk"><AgentStation id="risk" color={AGENTE_COLOR.risk} data={estaciones.risk} /></div>
            <div className="stage-slot s-monitoring"><AgentStation id="monitoring" color={AGENTE_COLOR.monitoring} data={estaciones.monitoring} /></div>
            <div className="stage-slot s-transaction"><AgentStation id="transaction" color={AGENTE_COLOR.transaction} data={estaciones.transaction} /></div>
            <div className="stage-slot s-explanation"><AgentStation id="explanation" color={AGENTE_COLOR.explanation} data={estaciones.explanation} /></div>
          </div>
        </main>

        {/* ---------- riel derecho ---------- */}
        <aside className="rail rail-r" aria-label="Estado y eventos">
          <Panel titulo="Flujo de transacciones" badge="en vivo">
            <ul className="flow-list">
              {(feed?.txs ?? []).slice(0, 5).map(t => (
                <li key={t.hash}>
                  <span className="flow-hash mono">{short(t.hash, 8)}</span>
                  <span className={t.value_eth >= 0 ? "flow-val" : "flow-val is-neg"}>
                    {t.value_eth >= 0 ? "+" : ""}
                    {t.value_eth} ETH
                  </span>
                  <span className="flow-score mono">score {t.score}</span>
                </li>
              ))}
              {feed?.txs?.length === 0 && <li className="empty">Esperando el primer bloque…</li>}
            </ul>
            <div className="flow-stats">
              <span>mediana {feed?.median_eth ?? "n/d"} ETH</span>
              <span>MAD {feed?.mad_eth ?? "n/d"}</span>
              <span>muestra {feed?.baseline_samples ?? 0}</span>
            </div>
          </Panel>

          <Panel titulo="Score máximo del bloque" alerta={riesgo !== null && riesgo >= 70}>
            <div className="score-row">
              <ScoreDial valor={riesgo} alerta={riesgo !== null && riesgo >= 70} />
              <ul className="score-legend">
                <li><span className="lg lg-ok" /> bajo &lt; 30</li>
                <li><span className="lg lg-warn" /> medio 30-69</li>
                <li><span className="lg lg-bad" /> alto ≥ 70</li>
              </ul>
            </div>
          </Panel>

          <Panel titulo="Nodo de IA" alerta={Boolean(ia?.estadisticas?.errors)}>
            <div className="ia-grid">
              <div><dt>proveedor</dt><dd>{ia?.provider ?? "—"}</dd></div>
              <div><dt>modelo</dt><dd className="mono">{ia?.model ?? "—"}</dd></div>
              <div><dt>éxito</dt><dd>{ia?.estadisticas?.ok ?? 0}</dd></div>
              <div><dt>rechazadas</dt><dd>{ia?.estadisticas?.rejected ?? 0}</dd></div>
              <div><dt>coste</dt><dd>${(ia?.estadisticas?.usd ?? 0).toFixed(4)}</dd></div>
              <div><dt>job ML</dt><dd>{status?.anomaly_job?.n_anomalies ?? "—"}</dd></div>
            </div>
          </Panel>

          <Panel titulo="Eventos recientes">
            <ul className="event-list">
              <AnimatePresence initial={false}>
                {eventos.map((e, i) => (
                  <motion.li
                    key={`${e.txt}-${i}`}
                    initial={{ opacity: 0, x: 14 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.35 }}
                    className={e.tipo}
                  >
                    <span className="ev-t mono">{e.t}</span>
                    <span className="ev-txt">{e.txt}</span>
                  </motion.li>
                ))}
              </AnimatePresence>
              {eventos.length === 0 && <li className="empty">Sin eventos todavía.</li>}
            </ul>
          </Panel>
        </aside>
      </div>

      {/* ---------- banda inferior ---------- */}
      <footer className="ops2-foot">
        <span className={sen?.enabled ? "foot-live is-on" : "foot-live"}>
          <span aria-hidden="true" /> Operación en curso
        </span>
        <span className="foot-agents">
          {orden.map((id, i) => (
            <span key={id} className="foot-agent" style={{ ["--c" as string]: AGENTE_COLOR[id] }} title={estaciones[id].titulo}>
              <AgentPixel id={id} color={AGENTE_COLOR[id]} size={22} carga={estaciones[id].progreso ?? 0.35} alarmed={estaciones[id].alerta} />
              <em>{i + 1}</em>
            </span>
          ))}
        </span>
        <span className="foot-meta mono">
          {status?.agentes?.length ?? 7} agentes · 1 objetivo · uptime {iso(uptime)}
          {sen?.telegram_configured ? " · telegram activo" : " · telegram sin configurar"}
        </span>
      </footer>
    </div>
  );
}

function Panel({
  titulo,
  children,
  badge,
  alerta,
}: {
  titulo: string;
  children: React.ReactNode;
  badge?: string;
  alerta?: boolean;
}) {
  return (
    <section className={alerta ? "panel is-alert" : "panel"}>
      <header className="panel-head">
        <h4>{titulo}</h4>
        {badge && <span className="panel-badge mono">{badge}</span>}
      </header>
      {children}
    </section>
  );
}

function Kpi({ etiqueta, valor, delta, alerta }: { etiqueta: string; valor: string; delta?: string; alerta?: boolean }) {
  return (
    <div className={alerta ? "kpi is-alert" : "kpi"}>
      <span className="kpi-label">{etiqueta}</span>
      <span className="kpi-value mono">{valor}</span>
      {delta && <span className="kpi-delta">{delta}</span>}
    </div>
  );
}
