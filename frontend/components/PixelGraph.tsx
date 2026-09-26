"use client";

import { useMemo } from "react";
import { circuloPixel, compilar, lineaPixel, rectanguloPixel, useFrame, type Frame } from "./pixel";

/**
 * Núcleo de inteligencia en píxeles.
 *
 * Lo mismo que antes —mismos datos, mismos paquetes viajando— pero dibujado
 * con cuadrados: los nodos son rombos de píxeles, las aristas son_lines de
 * peldaños y los paquetes son cuadros que se mueven. Sin curvas, sin
 * suavizado: se ve como un juego.
 */

const AZUL = "#1d4ed8";
const AZUL_CLARO = "#6f9bff";
const VERDE = "#15803d";
const AMBAR = "#b45309";
const ROJO = "#dc2626";
const BORDE = "#8fa3b8";

export type Tx = { hash: string; value_eth: number; score: number; flags: string[]; to: string | null };

type Props = {
  txs: Tx[];
  cadena?: string;
  ancho?: number;
  alto?: number;
};

type Nodo = { id: string; x: number; y: number; r: number; tipo: "core" | "wallet" | "ctr" | "alerta" };

const ANILLOS = [
  { r: 0.3, n: 6 },
  { r: 0.46, n: 8 },
  { r: 0.62, n: 6 },
];

export function PixelGraph({ txs, ancho = 420, alto = 300 }: Props) {
  const t = useFrame();
  const cx = ancho / 2;
  const cy = alto / 2;
  const maxR = Math.min(cx, cy) * 0.9;

  const nodos = useMemo<Nodo[]>(() => {
    const lista: Nodo[] = [{ id: "core", x: cx, y: cy, r: 9, tipo: "core" }];
    ANILLOS.forEach((a, ai) => {
      for (let i = 0; i < a.n; i++) {
        const ang = (i / a.n) * Math.PI * 2 - Math.PI / 2 + ai * 0.4;
        lista.push({
          id: `n${ai}-${i}`,
          x: Math.round(cx + Math.cos(ang) * maxR * a.r),
          y: Math.round(cy + Math.sin(ang) * maxR * a.r * 0.92),
          r: ai === 0 ? 3 : 2,
          tipo: ai === 0 ? "wallet" : "ctr",
        });
      }
    });
    txs.slice(0, 8).forEach((tx, i) => {
      const a = ANILLOS[1 + (i % 2)];
      const ang = (i / 8) * Math.PI * 2 - Math.PI / 2 + 0.2;
      const alerta = tx.score >= 55;
      lista.push({
        id: `t${i}`,
        x: Math.round(cx + Math.cos(ang) * maxR * (a.r + 0.1)),
        y: Math.round(cy + Math.sin(ang) * maxR * (a.r + 0.1) * 0.92),
        r: alerta ? 4 : 3,
        tipo: alerta ? "alerta" : "ctr",
      });
    });
    return lista;
  }, [cx, cy, maxR, txs]);

  const aristas = useMemo(
    () =>
      nodos.slice(1).map((n, i) => ({
        id: n.id,
        d: lineaPixel(cx, cy, n.x, n.y),
        alerta: n.tipo === "alerta",
        dur: `${2.4 + (i % 5) * 0.6}s`,
        begin: `${(i % 7) * 0.4}s`,
      })),
    [nodos, cx, cy],
  );

  const color = (n: Nodo) =>
    n.tipo === "alerta" ? ROJO : n.tipo === "core" ? AZUL : n.tipo === "wallet" ? AZUL_CLARO : AMBAR;

  return (
    <g aria-hidden="true">
      {/* aro de fondo, en píxeles */}
      <path d={circuloPixel(cx, cy, maxR * 0.78)} fill="#eef2f7" opacity={0.5} />
      <path
        d={circuloPixel(cx, cy, maxR * 0.78)}
        fill="none"
        stroke="#cbd5e1"
        strokeWidth={0.5}
        strokeDasharray="2 4"
      >
        <animateTransform
          attributeName="transform"
          type="rotate"
          from={`0 ${cx} ${cy}`}
          to={`360 ${cx} ${cy}`}
          dur="80s"
          repeatCount="indefinite"
        />
      </path>

      {/* aristas, cada una como peldaños de píxeles */}
      {aristas.map((a, i) => (
        <g key={a.id}>
          <path d={a.d} fill={a.alerta ? ROJO : BORDE} opacity={a.alerta ? 0.55 : 0.5} />
          {/* el paquete que viaja es una transacción real */}
          <rect
            x={-1.5}
            y={-1.5}
            width={3}
            height={3}
            fill={a.alerta ? ROJO : AZUL}
          >
            <animateMotion
              dur={a.dur}
              repeatCount="indefinite"
              begin={a.begin}
              path={`M${cx} ${cy} L${nodos[i + 1].x} ${nodos[i + 1].y}`}
              keyPoints="0;1"
              keyTimes="0;1"
              calcMode="linear"
            />
          </rect>
        </g>
      ))}

      {/* nodos: rombos de píxeles que laten */}
      {nodos.slice(1).map((n, i) => {
        const pulso = 1 + (Math.floor(t / 4) % 2 === i % 2 ? 0.35 : 0);
        const r = Math.round(n.r * pulso);
        return (
          <path
            key={n.id}
            d={circuloPixel(n.x, n.y, r)}
            fill={color(n)}
            opacity={0.9}
          />
        );
      })}

      {/* núcleo: cuadrado con el glifo, pulsando */}
      <g>
        <path d={rectanguloPixel(cx - 10, cy - 10, 20, 20)} fill={AZUL} />
        <path d={rectanguloPixel(cx - 7, cy - 6, 5, 11)} fill="#ffffff" />
        <path d={rectanguloPixel(cx + 2, cy - 6, 5, 11)} fill="#ffffff" />
        <path d={rectanguloPixel(cx - 7, cy + 1, 14, 4)} fill="#ffffff" />
        <path
          d={rectanguloPixel(cx - 13, cy - 13, 26, 26)}
          fill="none"
          stroke={AZUL}
          strokeWidth={1}
          opacity={0.25}
        >
          <animate
            attributeName="opacity"
            values="0.45;0.05;0.45"
            dur="3.4s"
            repeatCount="indefinite"
          />
        </path>
      </g>
    </g>
  );
}

export { compilar };
export type { Frame };
