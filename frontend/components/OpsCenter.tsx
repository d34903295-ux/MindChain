"use client";

import { useEffect, useState } from "react";

type Tx = { hash: string; from: string; to: string | null; value_eth: number; score: number; flags: string[]; alert: boolean };
type Feed = { latest: number; n_txs: number; n_alerts: number; txs: Tx[] };

/** Reloj de sala 24/7. Solo en cliente: el servidor renderiza un placeholder estable. */
function useRoomClock() {
  const [state, setState] = useState<{ time: string; mountedAt: number | null }>({
    time: "--:--:--",
    mountedAt: null,
  });
  useEffect(() => {
    const started = Date.now();
    const tick = () => {
      const d = new Date();
      const pad = (n: number) => String(n).padStart(2, "0");
      setState({
        time: `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`,
        mountedAt: started,
      });
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);
  return state;
}

type Station = {
  id: string;
  name: string;
  role: string;
  x: number;
  y: number;
  accent: string;
  status: "scanning" | "flagged" | "stable" | "review";
};

const STATIONS: Station[] = [
  { id: "wallet", name: "Wallet Agent", role: "Perfilando wallets", x: 150, y: 400, accent: "#2563eb", status: "scanning" },
  { id: "contract", name: "Contract Agent", role: "Permisos del bytecode", x: 1050, y: 400, accent: "#2563eb", status: "review" },
  { id: "transaction", name: "Transaction Agent", role: "Rastreando movimientos", x: 232, y: 592, accent: "#2563eb", status: "scanning" },
  { id: "research", name: "Research Agent", role: "Contexto y OSINT", x: 600, y: 246, accent: "#2563eb", status: "scanning" },
  { id: "risk", name: "Risk Agent", role: "Puntaje heurístico", x: 600, y: 566, accent: "#2563eb", status: "stable" },
  { id: "monitoring", name: "Monitoring Agent", role: "Vigila anomalías", x: 968, y: 592, accent: "#dc2626", status: "flagged" },
  { id: "explanation", name: "Explanation Agent", role: "Redacta el reporte", x: 1130, y: 690, accent: "#2563eb", status: "scanning" },
];

/** UMB con perspectiva isométrica (rotación X+Y estándar, sin assets). */
function UMB({ children, style, className }: { children: React.ReactNode; style?: React.CSSProperties; className?: string }) {
  return (
    <div className={className ? `umb ${className}` : "umb"} style={style}>
      {children}
    </div>
  );
}

function AgentSprite({ accent, status }: { accent: string; status: Station["status"] }) {
  return (
    <div className="agent-sprite" aria-hidden="true">
      <div className="agent-body" style={{ background: accent }}>
        <div className="agent-head" style={{ borderColor: accent }} />
        <div className="agent-monitor">
          <span style={{ background: accent }} />
          <span style={{ background: accent, opacity: 0.6 }} />
        </div>
      </div>
      {status === "scanning" && <span className="agent-ping" style={{ borderColor: accent }} />}
      {status === "flagged" && <span className="agent-alarm" style={{ borderColor: "#dc2626" }} />}
    </div>
  );
}

function Screen({ lines, alert, accent }: { lines: string[]; alert?: boolean; accent: string }) {
  return (
    <div className={`umb-screen${alert ? " is-alert" : ""}`}>
      <div className="umb-screen-top">
        <span style={{ background: alert ? "#dc2626" : accent }} />
        <span className="umb-screen-top-dim" />
      </div>
      <div className="umb-screen-body">
        {lines.map((l, i) => (
          <div className="umb-line" key={i} style={{ animationDelay: `${i * 260}ms` }}>
            <span className="umb-line-bar" style={{ background: alert && i === 0 ? "#dc2626" : accent, width: l }} />
          </div>
        ))}
      </div>
    </div>
  );
}

function StationCard({ s, feed }: { s: Station; feed: Feed | null }) {
  const top = feed?.txs?.[0];
  const lines =
    s.id === "wallet"
      ? ["72%", "58%", "44%", "31%"]
      : s.id === "contract"
        ? ["64%", "40%", "52%", "24%"]
        : s.id === "transaction"
          ? ["80%", "55%", "46%", "38%"]
          : s.id === "research"
            ? ["60%", "72%", "48%", "36%"]
            : s.id === "risk"
              ? ["46%", "68%", "82%", "40%"]
              : s.id === "monitoring"
                ? ["90%", "58%", "42%", "30%"]
                : ["70%", "52%", "62%", "44%"];
  const alert = s.status === "flagged" && (feed?.n_alerts ?? 0) > 0;
  return (
    <UMB className="umb-station" style={{ left: s.x, top: s.y }}>
      <div className="umb-label">
        <span className="umb-label-dot" style={{ background: alert ? "#dc2626" : "#16a34a" }} />
        <div>
          <strong>{s.name}</strong>
          <em>
            {top ? `${top.value_eth} ETH · score ${top.score}` : s.role}
          </em>
        </div>
      </div>
      <div className="umb-desk">
        <div className="umb-desk-top" />
        <div className="umb-desk-front" />
      </div>
      <div className="umb-screens">
        <Screen lines={lines} accent={s.accent} />
        <Screen lines={[...lines].reverse()} alert={alert} accent={s.accent} />
      </div>
      <AgentSprite accent={s.accent} status={s.status} />
    </UMB>
  );
}

function FlowGraph({ feed }: { feed: Feed | null }) {
  const txs = feed?.txs ?? [];
  const nodes = [
    { x: 470, y: 420, r: 7, kind: "core" as const },
    { x: 372, y: 360, r: 5, kind: "wallet" as const },
    { x: 560, y: 330, r: 5, kind: "wallet" as const },
    { x: 690, y: 372, r: 5, kind: "contract" as const },
    { x: 640, y: 470, r: 5, kind: "wallet" as const },
    { x: 430, y: 500, r: 5, kind: "wallet" as const },
    { x: 760, y: 452, r: 5, kind: "contract" as const },
    { x: 520, y: 540, r: 4, kind: "wallet" as const },
  ];
  const edges: [number, number][] = [
    [0, 1],
    [0, 2],
    [0, 3],
    [0, 4],
    [0, 5],
    [0, 6],
    [0, 7],
    [3, 6],
    [4, 7],
  ];
  const colors = { core: "#2563eb", wallet: "#16a34a", contract: "#b45309" };
  return (
    <div className="umb-table">
      <div className="umb-table-top">
        <svg viewBox="0 0 860 620" className="umb-graph" role="img" aria-label="Grafo de relaciones entre wallets y contratos, animado">
          <defs>
            <radialGradient id="coreGlow" cx="50%" cy="50%">
              <stop offset="0%" stopColor="#2563eb" stopOpacity="0.35" />
              <stop offset="100%" stopColor="#2563eb" stopOpacity="0" />
            </radialGradient>
          </defs>
          <circle cx={nodes[0].x} cy={nodes[0].y} r="90" fill="url(#coreGlow)">
            <animate attributeName="r" values="78;104;78" dur="6s" repeatCount="indefinite" />
          </circle>
          {edges.map(([a, b], i) => (
            <line
              key={i}
              x1={nodes[a].x}
              y1={nodes[a].y}
              x2={nodes[b].x}
              y2={nodes[b].y}
              stroke="#cbd5e1"
              strokeWidth="1.5"
            >
              <animate attributeName="stroke" values="#cbd5e1;#2563eb;#cbd5e1" dur={`${4 + i * 0.4}s`} repeatCount="indefinite" />
            </line>
          ))}
          {nodes.slice(1).map((n, i) => (
            <circle key={i} cx={n.x} cy={n.y} r={n.r} fill={colors[n.kind]}>
              <animateTransform
                attributeName="transform"
                type="translate"
                values={`0 0; ${i % 2 ? 6 : -6} ${i % 3 ? -5 : 5}; 0 0`}
                dur={`${3.5 + i * 0.3}s`}
                repeatCount="indefinite"
              />
            </circle>
          ))}
          {edges.slice(0, 6).map(([a, b], i) => {
            const A = nodes[a];
            const B = nodes[b];
            const d = txs[i % Math.max(txs.length, 1)];
            return (
              <circle key={`f${i}`} r="3.5" fill={d?.alert ? "#dc2626" : "#2563eb"}>
                <animateMotion
                  dur={`${3 + i * 0.35}s`}
                  repeatCount="indefinite"
                  path={`M${A.x},${A.y} L${B.x},${B.y}`}
                />
                <animate
                  attributeName="opacity"
                  values="0;1;0"
                  dur={`${3 + i * 0.35}s`}
                  repeatCount="indefinite"
                />
              </circle>
            );
          })}
          <g>
            <circle cx={nodes[0].x} cy={nodes[0].y} r="13" fill="#2563eb" />
            <path
              d={`M ${nodes[0].x} ${nodes[0].y - 9} L ${nodes[0].x + 7} ${nodes[0].y + 5} L ${nodes[0].x - 7} ${nodes[0].y + 5} Z`}
              fill="#fff"
            />
          </g>
        </svg>
        <div className="umb-table-legend">
          <span>
            <i style={{ background: "#2563eb" }} /> core
          </span>
          <span>
            <i style={{ background: "#16a34a" }} /> wallet
          </span>
          <span>
            <i style={{ background: "#b45309" }} /> contrato
          </span>
        </div>
      </div>
      <div className="umb-table-front" />
    </div>
  );
}

function WallBoard({ feed }: { feed: Feed | null }) {
  const txs = (feed?.txs ?? []).slice(0, 4);
  return (
    <div className="umb-wall-board">
      <div className="umb-board-head">
        <span className="umb-board-live" />
        Actividad en cadena ·{" "}
        {feed ? `bloque ${feed.latest}` : "conectando"}
      </div>
      <ul>
        {txs.length === 0 && <li className="is-empty">esperando transacciones…</li>}
        {txs.map((t, i) => (
          <li key={t.hash} style={{ animationDelay: `${i * 180}ms` }} className={t.alert ? "is-alert" : ""}>
            <span className="umb-board-score">{t.score}</span>
            <span className="umb-board-txt">
              {t.value_eth} ETH · {t.flags[0] ?? "transferencia"}
            </span>
            <span className="umb-board-hash">{t.hash.slice(0, 8)}…</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function OpsCenter() {
  const [feed, setFeed] = useState<Feed | null>(null);
  const { time, mountedAt } = useRoomClock();
  const session =
    mountedAt === null
      ? "sesión activa"
      : (() => {
          const mins = Math.floor((Date.now() - mountedAt) / 60000);
          return mins < 60 ? `${mins} min` : `${Math.floor(mins / 60)} h`;
        })();

  useEffect(() => {
    let alive = true;
    const tick = () => {
      fetch("http://localhost:8000/feed/ethereum?max_blocks=1")
        .then(r => (r.ok ? r.json() : Promise.reject()))
        .then((j: Feed) => {
          if (alive) setFeed(j);
        })
        .catch(() => undefined);
    };
    tick();
    const id = setInterval(tick, 12000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="ops" role="img" aria-label="Centro de inteligencia ChainMind: siete agentes de IA trabajan en una oficina isométrica y vigilan Ethereum en tiempo real">
      <div className="umb-room">
        <div className="umb-floor">
          <div className="umb-grid" />
          {STATIONS.map(s => (
            <StationCard key={s.id} s={s} feed={feed} />
          ))}
          <FlowGraph feed={feed} />
        </div>
        <div className="umb-wall umb-wall-back">
          <WallBoard feed={feed} />
        </div>
        <div className="umb-wall umb-wall-side">
          <div className="umb-side-panel">
            <span>BLOCKCHAIN</span>
            <strong>AI</strong>
            <span>OPS</span>
          </div>
        </div>
      </div>
      <div className="umb-desk-front-bar">
        <span className="umb-status">
          <i /> 7 agentes activos
        </span>
        <span className="umb-brand">ChainMind</span>
        <span className="umb-clock">
          {time} · {session}
        </span>
      </div>
    </div>
  );
}
