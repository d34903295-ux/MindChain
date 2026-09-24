"use client";

import { useEffect, useState } from "react";

type Tx = { hash: string; from: string; to: string | null; value_eth: number; score: number; flags: string[]; alert: boolean };
type Feed = { latest: number; n_txs: number; n_alerts: number; txs: Tx[] };

/* Geometría de la sala (viewBox 0 0 1200 820). Todo cabe: sin desbordes. */
const FLOOR = { cx: 600, cy: 470, hw: 520, hh: 250 };
const WALL_H = 150;

type Station = {
  id: string;
  name: string;
  metric: (f: Feed | null) => string;
  x: number;
  y: number;
  alert?: boolean;
  labelBelow?: boolean;
};

const STATIONS: Station[] = [
  { id: "research", name: "Research Agent", x: 600, y: 356, metric: () => "contexto y OSINT" },
  { id: "wallet", name: "Wallet Agent", x: 320, y: 380, metric: f => (f ? `${f.n_txs} txs en bloque` : "perfilando wallets") },
  { id: "contract", name: "Contract Agent", x: 880, y: 380, metric: () => "bytecode y permisos" },
  { id: "transaction", name: "Transaction Agent", x: 205, y: 520, metric: f => (f ? `${f.txs.length} movimientos` : "rastreando") },
  { id: "monitoring", name: "Monitoring Agent", x: 995, y: 520, alert: true, metric: f => (f ? `${f.n_alerts} alertas` : "vigilando") },
  { id: "risk", name: "Risk Agent", x: 455, y: 600, labelBelow: true, metric: f => (f ? `top score ${f.txs[0]?.score ?? 0}` : "puntaje") },
  { id: "explanation", name: "Explanation Agent", x: 745, y: 600, labelBelow: true, metric: () => "redactando reporte" },
];

function useRoomClock() {
  const [state, setState] = useState<{ time: string; started: number | null }>({
    time: "--:--:--",
    started: null,
  });
  useEffect(() => {
    const started = Date.now();
    const tick = () => {
      const d = new Date();
      const p = (n: number) => String(n).padStart(2, "0");
      setState({ time: `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`, started });
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);
  return state;
}

function floorPath(): string {
  const { cx, cy, hw, hh } = FLOOR;
  return `M${cx} ${cy - hh} L${cx + hw} ${cy} L${cx} ${cy + hh} L${cx - hw} ${cy} Z`;
}

function GridLines() {
  const { cx, cy, hw, hh } = FLOOR;
  const lines: JSX.Element[] = [];
  const N = 12;
  for (let i = 1; i < N; i++) {
    const t = i / N;
    // paralelas al eje izquierda-derecha
    const ax = cx - hw + t * hw * 2;
    const ayTop = cy - hh + t * hh * 2;
    const ayBot = cy + hh - t * hh * 2;
    lines.push(
      <line key={`h${i}`} x1={ax} y1={ayTop} x2={ax} y2={ayBot} className="ops-grid" />,
      <line key={`v${i}`} x1={cx - hw + t * hw * 2} y1={cy} x2={cx} y2={cy - hh + t * hh * 2} className="ops-grid" />,
      <line
        key={`v2${i}`}
        x1={cx - hw + t * hw * 2}
        y1={cy}
        x2={cx}
        y2={cy + hh - t * hh * 2}
        className="ops-grid"
      />
    );
  }
  return <g aria-hidden="true">{lines}</g>;
}

function Screen({ x, y, alert, seed }: { x: number; y: number; alert?: boolean; seed: number }) {
  const bars = [
    { w: 30, d: 2.6 },
    { w: 22, d: 3.1 },
    { w: 26, d: 2.2 },
  ];
  return (
    <g transform={`translate(${x},${y})`} aria-hidden="true">
      <rect x={-28} y={-24} width={56} height={42} rx={5} className="ops-screen" />
      <rect x={-22} y={-18} width={20} height={3} rx={1.5} fill={alert ? "#dc2626" : "#6f9bff"} />
      <rect x={-22} y={-11} width={12} height={3} rx={1.5} fill="#334155" />
      {bars.map((b, i) => (
        <rect key={i} x={-22} y={-3 + i * 7} height={3.5} rx={1.75} fill={alert && i === 0 ? "#dc2626" : "#2563eb"}>
          <animate
            attributeName="width"
            values={`${b.w * 0.25};${b.w + 8};${b.w * 0.25}`}
            dur={`${b.d + seed * 0.01}s`}
            repeatCount="indefinite"
          />
        </rect>
      ))}
    </g>
  );
}

function StationView({ s, feed }: { s: Station; feed: Feed | null }) {
  const isAlert = Boolean(s.alert && feed && feed.n_alerts > 0);
  return (
    <g className="ops-station" transform={`translate(${s.x},${s.y})`}>
      <title>{`${s.name} — ${s.metric(feed)}`}</title>
      {/* escritorio isométrico */}
      <polygon points="-58,0 0,-29 58,0 0,29" className="ops-desk-top" />
      <polygon points="-58,0 0,29 0,56 -58,27" className="ops-desk-left" />
      <polygon points="0,29 58,0 58,27 0,56" className="ops-desk-right" />
      {/* pantallas con pie anclado al escritorio */}
      <Screen x={-34} y={-70} alert={isAlert} seed={s.x} />
      <Screen x={34} y={-70} alert={false} seed={s.x + 3} />
      <line x1={-34} y1={-46} x2={-34} y2={-22} className="ops-stand" />
      <line x1={34} y1={-46} x2={34} y2={-22} className="ops-stand" />
      <line x1={-46} y1={-22} x2={46} y2={-22} className="ops-stand" />
      {/* avatar del agente */}
      <g transform="translate(0,-112)">
        <circle r={13} className="ops-avatar" />
        <circle r={4.5} fill={isAlert ? "#dc2626" : "#2563eb"} className="ops-avatar-core">
          {isAlert && (
            <animate attributeName="r" values="4.5;7;4.5" dur="1.6s" repeatCount="indefinite" />
          )}
        </circle>
        <path d="M-10 15 L-10 8 Q-10 3 0 3 Q10 3 10 8 L10 15 Z" className="ops-avatar-body" />
      </g>
      {/* etiqueta */}
      <g transform={`translate(0,${s.labelBelow ? 62 : -152})`}>
        <rect x={-66} y={-15} width={132} height={30} rx={9} className="ops-label-bg" />
        <text className="ops-label-name" textAnchor="middle" y={-2}>
          {s.name}
        </text>
        <text className="ops-label-metric" textAnchor="middle" y={10}>
          {s.metric(feed)}
        </text>
      </g>
      {s.labelBelow && <line x1={0} y1={30} x2={0} y2={47} className="ops-stand" />}
    </g>
  );
}

function Table({ feed }: { feed: Feed | null }) {
  const { cx, cy } = FLOOR;
  const nodes = [
    { x: 0, y: -6, r: 13, c: "#2563eb", core: true },
    { x: -104, y: -44, r: 7, c: "#16a34a" },
    { x: 8, y: -68, r: 7, c: "#16a34a" },
    { x: 116, y: -32, r: 7, c: "#b45309" },
    { x: -46, y: 46, r: 7, c: "#16a34a" },
    { x: 84, y: 44, r: 7, c: "#16a34a" },
    { x: -142, y: 16, r: 6, c: "#b45309" },
    { x: 156, y: 18, r: 6, c: "#b45309" },
  ];
  const edges: [number, number][] = [
    [0, 1], [0, 2], [0, 3], [0, 4], [0, 5], [0, 6], [0, 7], [3, 7], [4, 5],
  ];
  return (
    <g transform={`translate(${cx},${cy})`}>
      <title>Grafo de relaciones entre wallets y contratos</title>
      <polygon points="-190,0 0,-95 190,0 0,95" className="ops-table-top" />
      <polygon points="-190,0 0,95 0,124 -190,29" className="ops-table-left" />
      <polygon points="0,95 190,0 190,29 0,124" className="ops-table-right" />
      <g className="ops-table-grid" aria-hidden="true">
        {[-120, -60, 0, 60, 120].map(dx => (
          <line key={dx} x1={dx - 47} y1={-24} x2={dx + 47} y2={24} />
        ))}
        {[-60, 0, 60].map(dy => (
          <line key={dy} x1={-95} y1={dy + 47} x2={95} y2={dy - 47} />
        ))}
      </g>
      {edges.map(([a, b], i) => (
        <line key={i} x1={nodes[a].x} y1={nodes[a].y} x2={nodes[b].x} y2={nodes[b].y} className="ops-edge">
          <animate
            attributeName="stroke"
            values="#cbd5e1;#2563eb;#cbd5e1"
            dur={`${3.6 + i * 0.35}s`}
            repeatCount="indefinite"
          />
        </line>
      ))}
      {edges.slice(0, 6).map(([a, b], i) => {
        const t = feed?.txs[i];
        return (
          <circle key={`f${i}`} r={3.2} fill={t?.alert ? "#dc2626" : "#2563eb"}>
            <animateMotion
              dur={`${2.8 + i * 0.3}s`}
              repeatCount="indefinite"
              path={`M${nodes[a].x},${nodes[a].y} L${nodes[b].x},${nodes[b].y}`}
            />
            <animate attributeName="opacity" values="0;1;0" dur={`${2.8 + i * 0.3}s`} repeatCount="indefinite" />
          </circle>
        );
      })}
      {nodes.map((n, i) =>
        n.core ? null : (
          <circle key={i} cx={n.x} cy={n.y} r={n.r} fill={n.c}>
            <animateTransform
              attributeName="transform"
              type="translate"
              values={`0 0; ${i % 2 ? 5 : -5} ${i % 3 ? -4 : 4}; 0 0`}
              dur={`${3 + i * 0.3}s`}
              repeatCount="indefinite"
            />
          </circle>
        )
      )}
      <g>
        <circle cx={0} cy={-6} r={18} fill="#2563eb" />
        <path d="M0 -17 L9 4 L-9 4 Z" fill="#fff" />
        <circle cx={0} cy={-6} r={32} fill="none" stroke="#2563eb" strokeOpacity={0.25}>
          <animate attributeName="r" values="24;40;24" dur="5s" repeatCount="indefinite" />
          <animate attributeName="stroke-opacity" values="0.35;0.05;0.35" dur="5s" repeatCount="indefinite" />
        </circle>
      </g>
      <g className="ops-legend" transform="translate(-150, 80)">
        <rect x={-12} y={-11} width={152} height={19} rx={6} className="ops-legend-bg" />
        <circle cx={0} cy={-1.5} r={3.5} fill="#2563eb" />
        <text x={7} y={2}>core</text>
        <circle cx={44} cy={-1.5} r={3.5} fill="#16a34a" />
        <text x={51} y={2}>wallet</text>
        <circle cx={94} cy={-1.5} r={3.5} fill="#b45309" />
        <text x={101} y={2}>contrato</text>
      </g>
    </g>
  );
}

function Mural({ feed }: { feed: Feed | null }) {
  const txs = (feed?.txs ?? []).slice(0, 4);
  return (
    <g transform="translate(600,62)">
      <title>Actividad en cadena en tiempo real</title>
      <rect x={-300} y={0} width={600} height={104} rx={12} className="ops-mural" />
      <text x={-282} y={20} className="ops-mural-title">
        Actividad en cadena
        <tspan className="ops-mural-block">{feed ? ` · bloque ${feed.latest}` : " · conectando"}</tspan>
      </text>
      <circle cx={278} cy={15} r={4} className="ops-live-dot" />
      {txs.length === 0 && (
        <text x={-282} y={48} className="ops-mural-txt">
          esperando transacciones…
        </text>
      )}
      {txs.map((t, i) => (
        <g key={t.hash} transform={`translate(0, ${32 + i * 17})`} className="ops-mural-row">
          <rect x={-290} y={-9} width={580} height={16} rx={5} className={t.alert ? "ops-mural-line is-alert" : "ops-mural-line"} />
          <text x={-278} y={3} className={t.alert ? "ops-mural-score is-alert" : "ops-mural-score"}>
            {t.score}
          </text>
          <text x={-232} y={3} className="ops-mural-txt">
            {t.value_eth} ETH · {t.flags[0] ?? "transferencia"}
          </text>
          <text x={272} y={3} className="ops-mural-hash" textAnchor="end">
            {t.hash.slice(0, 8)}…
          </text>
        </g>
      ))}
    </g>
  );
}

export function OpsCenter() {
  const [feed, setFeed] = useState<Feed | null>(null);
  const { time, started } = useRoomClock();

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

  const mins = started === null ? null : Math.floor((Date.now() - started) / 60000);

  return (
    <div className="ops">
      <svg
        className="ops-svg"
        viewBox="0 0 1200 820"
        role="img"
        aria-label="Sala de operaciones de ChainMind: siete agentes de IA trabajan en una oficina isométrica y vigilan Ethereum en tiempo real"
      >
        <defs>
          <linearGradient id="opsFloor" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="100%" stopColor="#eef2f7" />
          </linearGradient>
          <linearGradient id="opsWall" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#fbfcfe" />
            <stop offset="100%" stopColor="#e7ecf2" />
          </linearGradient>
        </defs>

        {/* suelo */}
        <path d={floorPath()} fill="url(#opsFloor)" stroke="#dbe2ea" strokeWidth={1.5} />
        <g clipPath="url(#opsFloorClip)">
          <clipPath id="opsFloorClip">
            <path d={floorPath()} />
          </clipPath>
          <GridLines />
        </g>

        {/* paredes */}
        <polygon
          points={`${FLOOR.cx - FLOOR.hw},${FLOOR.cy} ${FLOOR.cx},${FLOOR.cy - FLOOR.hh} ${FLOOR.cx},${FLOOR.cy - FLOOR.hh - WALL_H} ${FLOOR.cx - FLOOR.hw},${FLOOR.cy - WALL_H}`}
          fill="url(#opsWall)"
          stroke="#e2e8f0"
          strokeWidth={1.5}
        />
        <polygon
          points={`${FLOOR.cx},${FLOOR.cy - FLOOR.hh} ${FLOOR.cx + FLOOR.hw},${FLOOR.cy} ${FLOOR.cx + FLOOR.hw},${FLOOR.cy - WALL_H} ${FLOOR.cx},${FLOOR.cy - FLOOR.hh - WALL_H}`}
          fill="#f2f5f9"
          stroke="#e2e8f0"
          strokeWidth={1.5}
        />
        <g aria-hidden="true">
          <rect x={1056} y={396} width={54} height={104} rx={8} className="ops-door" />
          <text x={1083} y={438} className="ops-door-text" textAnchor="middle">
            OPS
          </text>
          <text x={1083} y={456} className="ops-door-text" textAnchor="middle">
            24/7
          </text>
        </g>

        <Mural feed={feed} />
        <Table feed={feed} />
        {STATIONS.map(s => (
          <StationView key={s.id} s={s} feed={feed} />
        ))}

        {/* barra frontal */}
        <g transform="translate(600,766)">
          <rect x={-540} y={-30} width={1080} height={60} rx={14} className="ops-bar" />
          <circle cx={-508} cy={0} r={5} className="ops-bar-dot" />
          <text x={-492} y={4} className="ops-bar-text">
            7 agentes activos
          </text>
          <text x={0} y={5} className="ops-bar-brand" textAnchor="middle">
            ChainMind
          </text>
          <text x={508} y={4} className="ops-bar-text" textAnchor="end">
            {time} · {mins === null ? "sesión activa" : mins < 60 ? `${mins} min` : `${Math.floor(mins / 60)} h`}
          </text>
        </g>
      </svg>
    </div>
  );
}
