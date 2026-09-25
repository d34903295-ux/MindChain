"use client";

import { motion, useReducedMotion } from "framer-motion";
import { AgentPixel, type AgenteId } from "./AgentPixel";
import { IntelligenceCore } from "./IntelligenceCore";

/**
 * Planta de la sala: los agentes trabajando de verdad, a la vista.
 *
 * Antes el centro era solo un grafo. Esto es la misma sala vista desde
 * arriba, a la altura de un ojo: siete puestos alrededor de la mesa central,
 * y cada robot hace su ciclo de trabajo:
 *
 *   teclea en su puesto → recoge un paquete → camina a la mesa del núcleo →
 *   lo deja → vuelve a su puesto
 *
 * El grafo no desaparece: pasa a ser la superficie de la mesa central, que es
 * donde ocurre el trabajo. La leyenda y el bloque de Outside no se tocan; esto
 * solo sustituye a `IntelligenceCore` dentro de `.core-wrap`.
 *
 * Nada aquí es un adorno con reloj: el ritmo de cada robot sale de su carga
 * real (`carga`), y si un agente está alarmado su turno se acorta y late más.
 */

const COLOR: Record<string, string> = {
  wallet: "#1d4ed8",
  transaction: "#b45309",
  contract: "#7c3aed",
  research: "#0891b2",
  monitoring: "#dc2626",
  risk: "#db2777",
  explanation: "#0d9488",
};

type Puesto = { id: AgenteId; x: number; y: number; rot: number; fase: number; ritmo: number };

/** Puestos repartidos alrededor de la mesa. `fase` y `ritmo` desincronizan robots. */
const PUESTOS: Puesto[] = [
  { id: "research", x: 96, y: 104, rot: -14, fase: 0.0, ritmo: 26 },
  { id: "wallet", x: 310, y: 76, rot: 0, fase: 0.18, ritmo: 22 },
  { id: "contract", x: 524, y: 104, rot: 14, fase: 0.36, ritmo: 29 },
  { id: "risk", x: 60, y: 274, rot: -22, fase: 0.54, ritmo: 24 },
  { id: "monitoring", x: 560, y: 274, rot: 22, fase: 0.72, ritmo: 19 },
  { id: "transaction", x: 116, y: 438, rot: -10, fase: 0.87, ritmo: 21 },
  { id: "explanation", x: 504, y: 438, rot: 10, fase: 0.63, ritmo: 27 },
];

const NUCLEO = { x: 310, y: 270, r: 88 };

type Tx = {
  hash: string;
  value_eth: number;
  score: number;
  flags: string[];
  to: string | null;
};

type Props = {
  txs: Tx[];
  cadena: string;
  carga: Record<string, number>;
  alerta?: Record<string, boolean>;
  ancho?: number;
  alto?: number;
};

export function AgentFloor({ txs, cadena, carga, alerta, ancho = 620, alto = 520 }: Props) {
  // useReducedMotion devuelve boolean | null según la versión: aquí es bool
  const suave = Boolean(useReducedMotion());

  return (
    <svg
      viewBox={`0 0 ${ancho} ${alto}`}
      className="floor-svg"
      role="img"
      aria-label="Sala de operaciones vista desde arriba: siete agentes trabajan en sus puestos y se desplazan a la mesa central"
    >
      <defs>
        <radialGradient id="mesaTop" cx="50%" cy="40%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="70%" stopColor="#f6f8fc" />
          <stop offset="100%" stopColor="#e9eef5" />
        </radialGradient>
        <filter id="floorShadow" x="-30%" y="-30%" width="160%" height="160%">
          <feDropShadow dx="0" dy="6" stdDeviation="8" floodColor="#0f172a" floodOpacity="0.08" />
        </filter>
      </defs>

      {/* ---------------- suelo ---------------- */}
      <g aria-hidden="true">
        <rect x={0} y={0} width={ancho} height={alto} fill="#fbfcfe" />
        <path
          d={`M${ancho / 2} 8 L${ancho - 12} ${alto / 2} L${ancho / 2} ${alto - 8} L12 ${alto / 2} Z`}
          fill="#ffffff"
          stroke="#e6ebf2"
          strokeWidth={1.2}
        />
      </g>

      {/* ---------------- mesa central con el grafo ---------------- */}
      <g transform={`translate(${NUCLEO.x},${NUCLEO.y})`}>
        {/* patas / thickness de la mesa */}
        <ellipse cx={0} cy={10} rx={NUCLEO.r + 6} ry={(NUCLEO.r + 6) * 0.42} fill="#dfe6ee" />
        <ellipse cx={0} cy={4} rx={NUCLEO.r} ry={NUCLEO.r * 0.42} fill="#eef2f7" />
        <ellipse cx={0} cy={0} rx={NUCLEO.r} ry={NUCLEO.r * 0.42} fill="url(#mesaTop)" stroke="#d7dee7" strokeWidth={1.2} />
        <g filter="url(#floorShadow)">
          {/* el grafo es la superficie de la mesa: mismo componente, datos reales */}
          <svg
            x={-NUCLEO.r + 8}
            y={-NUCLEO.r * 0.42 - 4}
            width={(NUCLEO.r - 8) * 2}
            height={(NUCLEO.r - 8) * 0.84}
            viewBox="0 0 420 380"
            overflow="visible"
          >
            <IntelligenceCore txs={txs} cadena={cadena} ancho={420} alto={380} compacto />
          </svg>
        </g>
      </g>

      {/* ---------------- puestos ---------------- */}
      {PUESTOS.map(p => (
        <Puesto key={p.id} p={p} color={COLOR[p.id]} alarma={alerta?.[p.id] === true} suave={suave} />
      ))}

      {/* ---------------- robots en su ciclo de trabajo ---------------- */}
      {PUESTOS.map(p => (
        <Robot
          key={`robot-${p.id}`}
          p={p}
          color={COLOR[p.id]}
          carga={carga[p.id] ?? 0.5}
          alarma={alerta?.[p.id] === true}
          suave={suave}
        />
      ))}
    </svg>
  );
}

/* ------------------------------------------------------------------ puesto */
function Puesto({ p, color, alarma, suave }: { p: Puesto; color: string; alarma: boolean; suave: boolean }) {
  return (
    <g transform={`translate(${p.x},${p.y}) rotate(${p.rot})`} aria-hidden="true">
      {/* sombra del puesto */}
      <ellipse cx={0} cy={14} rx={36} ry={11} fill="#0f172a" opacity={0.05} />
      {/* tablero isométrico */}
      <polygon points="-36,0 0,-18 36,0 0,18" fill="#ffffff" stroke="#d7dee7" strokeWidth={1.1} />
      <polygon points="-36,0 0,18 0,25 -36,7" fill="#e7ecf2" stroke="#d3dae3" strokeWidth={1.1} />
      <polygon points="0,18 36,0 36,7 0,25" fill="#dde3ea" stroke="#cfd7e0" strokeWidth={1.1} />
      {/* línea de trabajo en el tablero */}
      <line x1={-24} y1={0} x2={24} y2={0} stroke={color} strokeOpacity={0.25} strokeWidth={1} />
      {/* monitor */}
      <g transform="translate(0,-25)">
        <rect x={-15} y={-16} width={30} height={21} rx={3} fill="#ffffff" stroke="#cfd7e0" strokeWidth={1.1} />
        <rect x={-12.5} y={-13.5} width={25} height={16} rx={2} fill={alarma ? "#fef2f2" : "#0f172a"} />
        <rect x={-10} y={-11} width={12} height={2.2} rx={1.1} fill={alarma ? "#dc2626" : color} />
        <rect x={-10} y={-7} width={8} height={2.2} rx={1.1} fill="#64748b" />
        <motion.rect
          x={-10}
          y={-3}
          width={16}
          height={2}
          rx={1}
          fill={alarma ? "#dc2626" : color}
          animate={suave ? {} : { width: [6, 18, 6] }}
          transition={{ duration: p.ritmo / 8, repeat: Infinity, ease: "easeInOut" }}
        />
        <line x1={0} y1={5} x2={0} y2={9} stroke="#cbd5e1" strokeWidth={1.6} strokeLinecap="round" />
      </g>
      {/* luz de estado del puesto */}
      <circle cx={25} cy={-3} r={2.8} fill={alarma ? "#dc2626" : color}>
        {alarma && !suave && (
          <animate attributeName="r" values="2.8;5;2.8" dur="1.4s" repeatCount="indefinite" />
        )}
      </circle>
      {/* nombre bajo el puesto */}
      <text y={38} textAnchor="middle" className="floor-station-name">
        {p.id}
      </text>
    </g>
  );
}

/* ------------------------------------------------------------------- robot */
function Robot({
  p,
  color,
  carga,
  alarma,
  suave,
}: {
  p: Puesto;
  color: string;
  carga: number;
  alarma: boolean;
  suave: boolean;
}) {
  // Punto de entrega en el anillo exterior de la mesa: camina hasta ahí, no encima.
  const entregaX = p.x + (NUCLEO.x - p.x) * 0.66;
  const entregaY = p.y + (NUCLEO.y - p.y) * 0.66 - 14;
  const dx = entregaX - p.x;
  const dy = entregaY - p.y;
  const lejos = Math.hypot(dx, dy) > 1;

  // Ciclo: puesto (teclea) → recoge paquete → mesa (deposita) → vuelve → puesto.
  const ciclo = suave
    ? { x: 0, y: 0 }
    : {
        x: [0, dx * 0.5, dx, dx * 0.5, 0, 0],
        y: [0, dy * 0.5, dy, dy * 0.5, 0, 0],
      };
  // mucho tiempo quieto (trabajando), poco caminando: es una sala, no unipe
  const tiempos = [0, 0.3, 0.4, 0.5, 0.82, 1];

  return (
    <g transform={`translate(${p.x},${p.y + 10})`}>
      <motion.g
        animate={ciclo}
        transition={{
          duration: p.ritmo,
          repeat: Infinity,
          times: tiempos,
          ease: "easeInOut",
          delay: p.fase * 8,
        }}
      >
        {/* el paquete que lleva: solo se ve mientras va hacia la mesa */}
        {!suave && lejos && (
          <g>
            <circle cx={0} cy={-2} r={3.2} fill={color} opacity={0.9}>
              <animate
                attributeName="opacity"
                values="0;1;1;0;0"
                dur={`${p.ritmo}s`}
                begin={`${p.fase * 8}s`}
                repeatCount="indefinite"
              />
            </circle>
            <circle cx={0} cy={-2} r={6} fill="none" stroke={color} strokeOpacity={0.5}>
              <animate
                attributeName="r"
                values="3;7;3"
                dur={`${p.ritmo / 3}s`}
                begin={`${p.fase * 8}s`}
                repeatCount="indefinite"
              />
              <animate
                attributeName="stroke-opacity"
                values="0.6;0;0.6"
                dur={`${p.ritmo / 3}s`}
                begin={`${p.fase * 8}s`}
                repeatCount="indefinite"
              />
            </circle>
          </g>
        )}
        {/* el robot: escala 1 para que se lea de verdad en la sala */}
        <g transform="scale(0.92)">
          <AgentPixel id={p.id} color={color} carga={carga} size={44} alarmed={alarma} />
        </g>
      </motion.g>
    </g>
  );
}
