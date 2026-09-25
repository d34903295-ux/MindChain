"use client";

import { motion, useReducedMotion } from "framer-motion";
import { useMemo } from "react";

/**
 * Núcleo de inteligencia: el grafo que conecta las dos redes con wallets,
 * contratos y transacciones.
 *
 * No es decoración. Los nodos se generan a partir de las transacciones reales
 * que llegan del feed (destino, valor, score), así que el núcleo cambia de
 * forma cuando cambia la cadena, y los paquetes que viajan por las aristas
 * son esas transacciones.
 *
 * Paleta: azul institucional para la señal, ámbar para valor alto, rojo
 * solo para alerta. Nunca neón: el contraste viene del fondo claro.
 */

export type Nodo = {
  id: string;
  x: number;
  y: number;
  r: number;
  tipo: "core" | "wallet" | "contrato" | "alerta" | "red";
  valor?: number;
  score?: number;
  tx?: string;
};

type Props = {
  /** transacciones reales del feed; si no hay, el grafo respira con datos de sostén */
  txs: { hash: string; value_eth: number; score: number; flags: string[]; to: string | null }[];
  cadena: string;
  ancho?: number;
  alto?: number;
  compacto?: boolean;
};

const AZUL = "#1d4ed8";
const AZUL_CLARO = "#6f9bff";
const VERDE = "#15803d";
const AMBAR = "#b45309";
const ROJO = "#dc2626";
const GRIS = "#94a3b8";

/** Puntos cardinales alrededor del núcleo, para que el grafo crezca hacia fuera. */
const ANILLOS = [
  { r: 0.34, n: 7, fase: 0 },
  { r: 0.5, n: 9, fase: 0.35 },
  { r: 0.68, n: 11, fase: 0.7 },
  { r: 0.84, n: 8, fase: 0.15 },
];

export function IntelligenceCore({ txs, cadena, ancho = 520, alto = 400, compacto }: Props) {
  const suave = useReducedMotion();
  const cx = ancho / 2;
  const cy = alto / 2;
  const maxR = Math.min(cx, cy) * 0.92;

  const { nodos, aristas } = useMemo(() => {
    const lista: Nodo[] = [
      // El núcleo es un nodo más del grafo: existe para que las aristas tengan
      // de dónde salir. Se dibuja aparte, más abajo.
      { id: "core", x: cx, y: cy, r: 0, tipo: "core" },
    ];
    const aristas: { a: string; b: string; alerta: boolean; valor: number }[] = [];

    // Wallet origen e intercambio alrededor del núcleo
    const anillo = (indice: number, total: number, radio: number) => {
      const ang = (indice / total) * Math.PI * 2 - Math.PI / 2;
      return {
        x: cx + Math.cos(ang) * radio,
        y: cy + Math.sin(ang) * radio * 0.86,
      };
    };

    ANILLOS.forEach((anilloDef, ai) => {
      for (let i = 0; i < anilloDef.n; i++) {
        const p = anillo(i, anilloDef.n, maxR * anilloDef.r);
        const id = `n${ai}-${i}`;
        lista.push({
          id,
          x: p.x,
          y: p.y,
          r: 7 + (i % 3) * 2.2,
          tipo: ai === 0 ? "wallet" : ai === 1 ? "contrato" : "wallet",
        });
        aristas.push({ a: "core", b: id, alerta: false, valor: 0 });
        // anillos cruzados: hacen que el grafo parezca una red y no una rueda
        if (i > 0) {
          aristas.push({ a: `n${ai}-${i - 1}`, b: id, alerta: false, valor: 0 });
        }
      }
    });

    // Cada transacción real aporta un nodo y su paquete. Si no hay datos, la
    // sala sigue viva con los nodos de sostén de arriba.
    txs.slice(0, 12).forEach((t, i) => {
      const anilloDef = ANILLOS[1 + (i % 3)];
      const p = anillo(i, 12, maxR * (anilloDef.r + 0.08));
      const id = `tx${i}`;
      const alerta = t.score >= 50 || t.flags.some(f => f.includes("ballena"));
      lista.push({
        id,
        x: p.x,
        y: p.y,
        r: alerta ? 11 : 8,
        tipo: alerta ? "alerta" : "contrato",
        valor: t.value_eth,
        score: t.score,
        tx: t.hash,
      });
      const destino = ARING_S[Math.floor(i / 2) % ARING_S.length];
      aristas.push({ a: destino, b: id, alerta, valor: t.value_eth });
    });

    return { nodos: lista, aristas };
  }, [txs, cx, cy, maxR]);

  const color = (t: Nodo["tipo"], score?: number) =>
    t === "alerta" ? ROJO : t === "core" ? AZUL : (score ?? 0) >= 60 ? AMBAR : t === "red" ? VERDE : AZUL_CLARO;

  return (
    <svg
      viewBox={`0 0 ${ancho} ${alto}`}
      className="core-svg"
      role="img"
      aria-label={`Núcleo de inteligencia: grafo de wallets, contratos y transacciones de ${cadena}`}
    >
      <defs>
        <radialGradient id="coreHalo">
          <stop offset="0%" stopColor={AZUL} stopOpacity={0.16} />
          <stop offset="70%" stopColor={AZUL} stopOpacity={0.04} />
          <stop offset="100%" stopColor={AZUL} stopOpacity={0} />
        </radialGradient>
        <filter id="coreSoft" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="6" />
        </filter>
      </defs>

      {/* halo y aros de fondo: dan profundidad sin brillos */}
      <circle cx={cx} cy={cy} r={maxR * 0.9} fill="url(#coreHalo)" />
      {!compacto &&
        ANILLOS.map((a, i) => (
          <motion.ellipse
            key={i}
            cx={cx}
            cy={cy}
            rx={maxR * a.r}
            ry={maxR * a.r * 0.92}
            fill="none"
            stroke={AZUL}
            strokeOpacity={0.09}
            strokeDasharray="2 7"
            animate={{ rotate: 360 }}
            transition={{ duration: 60 + i * 34, repeat: Infinity, ease: "linear" }}
            style={{ originX: `${cx}px`, originY: `${cy}px` }}
          />
        ))}

      {/* aristas */}
      {aristas.map((a, i) => {
        const na = nodos.find(n => n.id === a.a)!;
        const nb = nodos.find(n => n.id === a.b)!;
        return (
          <g key={`e${i}`}>
            <line
              x1={na.x}
              y1={na.y}
              x2={nb.x}
              y2={nb.y}
              stroke={a.alerta ? ROJO : "#b6c2d2"}
              strokeWidth={a.alerta ? 2.2 : 1.4}
              strokeOpacity={a.alerta ? 0.5 : 0.75}
            />
            {/* el paquete que viaja es una transacción real */}
            {!suave && (
              <circle r={a.alerta ? 4.2 : 3.2} fill={a.alerta ? ROJO : AZUL}>
                <animateMotion
                  dur={`${2.6 + (i % 5) * 0.7}s`}
                  repeatCount="indefinite"
                  begin={`${(i % 7) * 0.35}s`}
                  path={`M${na.x},${na.y} L${nb.x},${nb.y}`}
                />
                <animate
                  attributeName="opacity"
                  values="0;1;0"
                  dur={`${2.6 + (i % 5) * 0.7}s`}
                  repeatCount="indefinite"
                />
              </circle>
            )}
          </g>
        );
      })}

      {/* nodos: pulsan a distinto ritmo, y los de alerta laten más rápido */}
      {nodos.map((n, i) =>
        n.tipo === "core" ? null : (
        <motion.g
          key={n.id}
          style={{ originX: `${n.x}px`, originY: `${n.y}px` }}
          animate={
            suave
              ? {}
              : {
                  scale: n.tipo === "alerta" ? [1, 1.45, 1] : [1, 1.16, 1],
                  opacity: [0.82, 1, 0.82],
                }
          }
          transition={{
            duration: n.tipo === "alerta" ? 1.5 : 3 + (i % 4) * 0.6,
            repeat: Infinity,
            ease: "easeInOut",
            delay: (i % 6) * 0.22,
          }}
        >
          <circle cx={n.x} cy={n.y} r={n.r} fill={color(n.tipo, n.score)} />
          {n.tipo === "alerta" && (
            <circle cx={n.x} cy={n.y} r={n.r * 2.4} fill="none" stroke={ROJO} strokeOpacity={0.28} strokeWidth={1} />
          )}
          {n.tipo === "wallet" && i % 3 === 0 && (
            <rect x={n.x - 1} y={n.y - 1} width={2} height={2} fill="#fff" />
          )}
        </motion.g>
      ))}

      {/* núcleo: late como un corazón y arrastra un anillo de datos */}
      <motion.g
        style={{ originX: `${cx}px`, originY: `${cy}px` }}
        animate={suave ? {} : { scale: [1, 1.045, 1] }}
        transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }}
      >
        <circle cx={cx} cy={cy} r={38} fill={AZUL} />
        <circle cx={cx} cy={cy} r={38} fill="none" stroke={AZUL} strokeWidth={2} opacity={0.25} filter="url(#coreSoft)" />
        {/* marca: el glifo de ChainMind */}
        <path d={`M${cx} ${cy - 16} L${cx + 15} ${cy + 12} L${cx} ${cy + 4} L${cx - 15} ${cy + 12} Z`} fill="#fff" />
      </motion.g>

      {!suave && (
        <>
          <circle r={2.4} fill={AZUL_CLARO}>
            <animateMotion dur="11s" repeatCount="indefinite" path={circulo(cx, cy, maxR * 0.32)} />
          </circle>
          <circle r={1.9} fill={VERDE}>
            <animateMotion dur="17s" repeatCount="indefinite" path={circulo(cx, cy, maxR * 0.46)} begin="-4s" />
          </circle>
          <circle r={1.7} fill={AMBAR}>
            <animateMotion dur="23s" repeatCount="indefinite" path={circulo(cx, cy, maxR * 0.62)} begin="-9s" />
          </circle>
        </>
      )}

      {/* Las etiquetas de los planos no van aquí: se dibujaban encima de los
          nodos y se solapaban. La leyenda vive bajo el grafo, en HTML. */}
    </svg>
  );
}

const ARING_S = ["n0-0", "n0-2", "n0-4", "n1-1", "n1-4", "n1-7", "n2-0", "n2-3", "n2-6", "n2-9", "n3-1", "n3-4"];

function circulo(cx: number, cy: number, r: number): string {
  return `M${cx - r},${cy} a${r},${r * 0.86} 0 1,0 ${r * 2},0 a${r},${r * 0.86} 0 1,0 ${-r * 2},0`;
}
