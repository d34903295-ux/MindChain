"use client";

import { useReducedMotion } from "framer-motion";
import { memo, useEffect, useMemo, useRef, useState } from "react";
import { AgentePixel, type AgenteId, type Postura } from "./AgentePixel";
import { faseEnCiclo, modoEnCiclo, posicionEnCiclo } from "./movimiento";
import { PixelGraph } from "./PixelGraph";
import { circuloPixel, lineaPixel, rectanguloPixel, romboPixel, useFrame } from "./pixel";

/**
 * La sala vista desde arriba, en pixel art.
 *
 * Antes era un grafo con una mesa. Ahora es una oficina: suelo de baldosas
 * isométricas con alfombra, pared con ventanas y skyline, siete escritorios de
 * madera y siete agentes que teclean, caminan, saludan y vuelven cargando.
 *
 * Todo son cuadrados. Las líneas del suelo, los monitores, los robots y las
 * conducciones de datos están hechos con la misma rejilla de píxeles, y el
 * SVG va con `shape-rendering: crispEdges` en el CSS para que el navegador no
 * suavice nada. Sin eso, pixel art no hay.
 *
 * El grafo no desaparece: es la superficie de proyección de la mesa central.
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

type Puesto = {
  id: AgenteId;
  x: number;
  y: number;
  fase: number;
  periodo: number;
  ritmo: number;
  ruta: [number, number][];
};

type Tx = { hash: string; value_eth: number; score: number; flags: string[]; to: string | null };

type Props = {
  txs: Tx[];
  cadena: string;
  carga: Record<string, number>;
  alerta?: Record<string, boolean>;
  ancho?: number;
  alto?: number;
};

const ORDEN = [
  "research",
  "wallet",
  "contract",
  "monitoring",
  "explanation",
  "transaction",
  "risk",
] as const;

const DESPLAZE = 18;

export function AgentFloor({ txs, cadena, carga, alerta, ancho = 600, alto = 480 }: Props) {
  const suave = Boolean(useReducedMotion());
  const caja = useRef<HTMLDivElement>(null);
  const [medida, setMedida] = useState({ w: ancho, h: alto });

  useEffect(() => {
    const el = caja.current;
    if (!el) return;
    const medir = () => {
      const r = el.getBoundingClientRect();
      if (r.width > 24 && r.height > 24) {
        const w = Math.round(r.width);
        const h = Math.round(r.height);
        setMedida(prev => (prev.w === w && prev.h === h ? prev : { w, h }));
      }
    };
    medir();
    const ro = new ResizeObserver(medir);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const w = medida.w;
  const h = medida.h;
  const min = Math.min(w, h);
  const nuc = { x: w / 2, y: h / 2 + 6, r: Math.max(36, Math.min(min * 0.27, 96)) };
  const escala = min < 300 ? 2 : 3;

  const puestos = useMemo<Puesto[]>(() => {
    const rx = Math.max(20, w / 2 - 38);
    const ry = Math.max(26, h / 2 - 46);
    return ORDEN.map((id, i) => {
      const ang = -Math.PI / 2 + (i * Math.PI * 2) / ORDEN.length;
      const x = Math.round(w / 2 + Math.cos(ang) * rx);
      const y = Math.round(h / 2 + 6 + Math.sin(ang) * ry);
      const dx = nuc.x - x;
      const dy = nuc.y - y;
      return {
        id,
        x,
        y,
        fase: (i * 0.137) % 1,
        periodo: 240 + (i % 3) * 40,
        ritmo: 2.2 + (i % 3) * 0.5,
        ruta: [
          [0, 0],
          [Math.round(dx * 0.34), Math.round(dy * 0.34)],
          [Math.round(dx * 0.58), Math.round(dy * 0.58)],
        ],
      };
    });
  }, [w, h, nuc.x, nuc.y]);

  return (
    <div className="floor-box" ref={caja}>
      <svg
        viewBox={`0 0 ${w} ${h}`}
        className="floor-svg"
        shapeRendering="crispEdges"
        role="img"
        aria-label="Sala de operaciones en pixel art: siete agentes teclean, caminan a la mesa central y vuelven con el paquete"
      >
        <defs>
          <radialGradient id="nucleoLuz" cx="0.5" cy="0.5" r="0.5">
            <stop offset="0%" stopColor="#6f9bff" stopOpacity="0.34" />
            <stop offset="55%" stopColor="#6f9bff" stopOpacity="0.10" />
            <stop offset="100%" stopColor="#6f9bff" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="sueloLuz" cx="0.5" cy="0.5" r="0.5">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0.9" />
            <stop offset="70%" stopColor="#ffffff" stopOpacity="0.25" />
            <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
          </radialGradient>
        </defs>

        <Suelo w={w} h={h} nuc={nuc} suave={suave} />
        <ConoDeLuz nuc={nuc} />

        {puestos.map(p => (
          <Camino
            key={`cam-${p.id}`}
            id={p.id}
            color={COLOR[p.id]}
            desde={[p.x, p.y + DESPLAZE]}
            hasta={[nuc.x, nuc.y]}
            fase={(ORDEN.indexOf(p.id) * 0.137) % 1}
            suave={suave}
          />
        ))}

        <MesaCentral txs={txs} cadena={cadena} nuc={nuc} suave={suave} />

        {puestos.map(p => (
          <PuestoMesa
            key={p.id}
            p={p}
            color={COLOR[p.id]}
            alarma={alerta?.[p.id] === true}
            carga={carga[p.id] ?? 0.5}
            nuc={nuc}
            suave={suave}
          />
        ))}

        {puestos.map(p => (
          <Robot
            key={`r-${p.id}`}
            p={p}
            color={COLOR[p.id]}
            carga={carga[p.id] ?? 0.5}
            alarma={alerta?.[p.id] === true}
            escala={escala}
            suave={suave}
          />
        ))}

        <Lampara nuc={nuc} />
      </svg>
    </div>
  );
}

/* -------------------------------------------------------------------- suelo */
const Suelo = memo(function Suelo({
  w,
  h,
  nuc,
  suave,
}: {
  w: number;
  h: number;
  nuc: { x: number; y: number; r: number };
  suave: boolean;
}) {
  const RX = w < 380 ? 22 : 30;
  const RY = RX / 2;
  const cx = Math.round(nuc.x);
  const cy = Math.round(nuc.y);

  const capas = useMemo(() => {
    let clara = "";
    let oscura = "";
    const filas = Math.ceil(h / RY) + 2;
    const cols = Math.ceil(w / RX) + 3;
    for (let f = -1; f < filas; f++) {
      for (let c = -1; c < cols; c++) {
        const x = Math.round(c * RX + (f % 2 ? RX / 2 : 0));
        const y = f * RY;
        if (y < -RY * 2 || y > h + RY) continue;
        if (x < -RX * 2 || x > w + RX) continue;
        const d = romboPixel(x, y, RX, RY);
        if ((f + c) % 2 === 0) clara += d;
        else oscura += d;
      }
    }

    let rayas = "";
    for (let x = -h; x < w + h; x += RX * 2) {
      rayas += lineaPixel(x, 0, x + h, h);
      rayas += lineaPixel(x, h, x + h, 0);
    }

    const pared = 16;
    const ventanas: string[] = [];
    const skyline: string[] = [];
    const marco: string[] = [];
    for (let x = 6; x < w - 20; x += 34) {
      const ancho = Math.min(24, w - 14 - x);
      if (ancho < 10) break;
      ventanas.push(rectanguloPixel(x, 4, ancho, 7));
      for (let b = 0; b < 3; b++) {
        const bx = x + 1 + b * Math.floor((ancho - 2) / 3);
        const bh = 2 + ((b * 3) % 3);
        skyline.push(rectanguloPixel(bx, 11 - bh, Math.floor((ancho - 2) / 3) - 1, bh));
      }
      marco.push(rectanguloPixel(x - 1, 3, ancho + 2, 9));
      marco.push(rectanguloPixel(x + Math.floor(ancho / 2), 4, 1, 7));
    }

    const R = Math.round(Math.min(w, h) * 0.42);
    const alfombraBorde = romboPixel(cx, cy, R + 4, (R + 4) * 0.5);
    const alfombra = romboPixel(cx, cy, R, R * 0.5);
    const alfombraRayas =
      romboPixel(cx, cy, R - 8, (R - 8) * 0.5) + romboPixel(cx, cy, R - 24, (R - 24) * 0.5);
    const alfombraInterior = romboPixel(cx, cy, R - 16, (R - 16) * 0.5);

    const sombraPared =
      rectanguloPixel(0, pared, w, 1) +
      rectanguloPixel(0, pared + 1, w, 1) +
      rectanguloPixel(0, pared + 2, w, 1);

    return {
      clara,
      oscura,
      rayas,
      pared,
      ventanas: ventanas.join(""),
      skyline: skyline.join(""),
      marco: marco.join(""),
      alfombra,
      alfombraBorde,
      alfombraInterior,
      alfombraRayas,
      sombraPared,
    };
  }, [w, h, RX, RY, cx, cy]);

  return (
    <g aria-hidden="true">
      <path d={rectanguloPixel(0, 0, w, h)} fill="#e6ebf2" />
      <circle cx={cx} cy={cy} r={Math.max(w, h) * 0.62} fill="url(#sueloLuz)" />
      <circle cx={cx} cy={cy} r={Math.max(w, h) * 0.5} fill="url(#nucleoLuz)" />
      <path d={capas.oscura} fill="#dbe2ea" />
      <path d={capas.clara} fill="#eef2f7" />
      <path d={capas.rayas} fill="#ccd6e1" opacity={0.6} />

      {/* alfombra de la zona de mesa: separa el centro del resto */}
      <path d={capas.alfombraBorde} fill="#a9c2ec" />
      <path d={capas.alfombra} fill="#c5d8f7" />
      <path d={capas.alfombraRayas} fill="#d6e4fb" />
      <path d={capas.alfombraInterior} fill="#bcd1f5" />
      <path d={capas.sombraPared} fill="#64748b" opacity={0.16} />

      <path d={rectanguloPixel(0, 0, w, capas.pared)} fill="#cbd6e3" />
      <path d={rectanguloPixel(0, 0, w, 3)} fill="#dae3ed" />
      <path d={rectanguloPixel(0, capas.pared - 2, w, 2)} fill="#94a3b8" />
      <path d={capas.ventanas} fill="#bfe3ff" />
      <path d={capas.skyline} fill="#9db4c9" />
      <path d={capas.marco} fill="#7c8ba0" />
      <path d={rectanguloPixel(0, capas.pared + 3, w, 1)} fill="#b6c4d6" opacity={0.5} />

      {/* marco de la habitacion: el suelo no se pierde por los bordes */}
      <path d={rectanguloPixel(0, 0, w, 2)} fill="#b6c4d6" />
      <path d={rectanguloPixel(0, 0, 2, h)} fill="#c2cedd" />
      <path d={rectanguloPixel(w - 2, 0, 2, h)} fill="#c2cedd" />
      <path d={rectanguloPixel(0, h - 3, w, 3)} fill="#a9b7c8" />
      <path d={rectanguloPixel(0, h - 5, w, 2)} fill="#c2cedd" opacity={0.7} />

      <Rack x={6} y={capas.pared + 7} />
      <Rack x={w - 30} y={capas.pared + 7} />
      {w > 200 && <Reloj x={w - 54} y={capas.pared / 2 - 1} suave={suave} />}
      <Planta x={w - 15} y={h - 13} />
      <Planta x={8} y={h - 12} />
    </g>
  );
});

/* -------------------------------------------------------------------- reloj */
/** Reloj de pared con la hora real: la sala no está congelada. */
function Reloj({ x, y, suave }: { x: number; y: number; suave: boolean }) {
  const t = useFrame();
  const ahora = new Date();
  const seg = ahora.getSeconds() + (suave ? 0 : (t % 60) / 60);
  const min = ahora.getMinutes() + seg / 60;
  const hora = (ahora.getHours() % 12) + min / 60;
  const ang = (v: number, vueltas: number) => (v / vueltas) * 360;
  return (
    <g>
      <path d={circuloPixel(x, y, 7)} fill="#7c8ba0" />
      <path d={circuloPixel(x, y, 6)} fill="#f8fafc" />
      <path d={rectanguloPixel(x - 1, y - 5, 1, 1)} fill="#94a3b8" />
      <path d={rectanguloPixel(x + 1, y, 1, 1)} fill="#94a3b8" />
      <path d={rectanguloPixel(x - 1, y + 4, 1, 1)} fill="#94a3b8" />
      <path d={rectanguloPixel(x - 2, y, 1, 1)} fill="#94a3b8" />
      <g transform={`rotate(${ang(hora, 12)} ${x} ${y})`}>
        <path d={rectanguloPixel(x - 1, y - 4, 2, 4)} fill="#334155" />
      </g>
      <g transform={`rotate(${ang(min, 60)} ${x} ${y})`}>
        <path d={rectanguloPixel(x - 1, y - 6, 1, 6)} fill="#dc2626" />
      </g>
      <path d={rectanguloPixel(x - 1, y - 1, 2, 2)} fill="#0f172a" />
    </g>
  );
}

function Rack({ x, y }: { x: number; y: number }) {
  return (
    <g>
      <path d={rectanguloPixel(x - 1, y - 1, 24, 20)} fill="#b6c4d6" />
      <path d={rectanguloPixel(x, y, 22, 18)} fill="#334155" />
      {[0, 6, 12].map(f => (
        <g key={f}>
          <path d={rectanguloPixel(x + 2, y + f, 18, 4)} fill="#1e293b" />
          <path
            d={rectanguloPixel(x + 15, y + f + 1, 2, 2)}
            fill={f % 2 === 0 ? "#4ade80" : "#60a5fa"}
            className="rack-led"
          />
        </g>
      ))}
    </g>
  );
}

function Planta({ x, y }: { x: number; y: number }) {
  return (
    <g>
      <path d={rectanguloPixel(x - 7, y - 3, 14, 2)} fill="#92400e" />
      <path d={rectanguloPixel(x - 6, y - 2, 12, 6)} fill="#b45309" />
      <path d={rectanguloPixel(x - 1, y - 12, 2, 10)} fill="#15803d" />
      <path d={rectanguloPixel(x - 5, y - 10, 4, 3)} fill="#22c55e" />
      <path d={rectanguloPixel(x + 2, y - 8, 4, 3)} fill="#16a34a" />
      <path d={rectanguloPixel(x - 3, y - 15, 3, 4)} fill="#22c55e" />
    </g>
  );
}

/* ------------------------------------------------------------------ lampara */
/** Lámpara colgante sobre la mesa, en dos capas: el cono de luz se dibuja con
 *  el suelo (ilumina la alfombra) y la pantalla cuelga al final de todo, que
 *  es lo más cercano a la cámara. Con una sola capa, el escritorio de research
 *  —que está justo encima de la mesa— la tapaba entera. */
const colgarDesde = (nuc: { y: number; r: number }): number =>
  Math.max(28, nuc.y - nuc.r - 10);

function ConoDeLuz({ nuc }: { nuc: { x: number; y: number; r: number } }) {
  const x = Math.round(nuc.x);
  const y = Math.round(nuc.y);
  const r = nuc.r;
  const bajo = colgarDesde(nuc);
  return (
    <path
      d={`M${x - 14} ${bajo + 6}L${x + 14} ${bajo + 6}L${x + r} ${y + r * 0.45}L${x - r} ${y + r * 0.45}Z`}
      fill="#fef3c7"
      opacity={0.14}
      aria-hidden="true"
    />
  );
}

function Lampara({ nuc }: { nuc: { x: number; y: number; r: number } }) {
  const x = Math.round(nuc.x);
  const bajo = colgarDesde(nuc);
  const techo = 18;
  return (
    <g aria-hidden="true">
      <path d={rectanguloPixel(x - 1, techo, 2, Math.max(8, bajo - techo))} fill="#8fa3b8" />
      <path d={romboPixel(x, bajo + 8, 17, 8)} fill="#a9713c" />
      <path d={romboPixel(x, bajo + 5, 13, 6)} fill="#c68a4c" />
      <path d={romboPixel(x, bajo + 3, 8, 4)} fill="#fde68a" />
    </g>
  );
}

/* ------------------------------------------------------------------ camino */
/* Cada puesto tiene su camino de datos hasta la mesa: un surco de píxeles por
   el suelo y un paquete que viaja siempre (los datos que el agente manda al
   núcleo). El paquete va a su ritmo, así que los siete nunca van en bloque. */
function Camino({
  id,
  color,
  desde,
  hasta,
  fase,
  suave,
}: {
  id: AgenteId;
  color: string;
  desde: [number, number];
  hasta: [number, number];
  fase: number;
  suave: boolean;
}) {
  const t = useFrame();
  const paso = 70 + ((ORDEN.indexOf(id) ** 2) % 5) * 16;
  const avance = suave ? 0 : (t / paso + fase) % 1;

  const dx = hasta[0] - desde[0];
  const dy = hasta[1] - desde[1];
  const px = Math.round(desde[0] + dx * avance);
  const py = Math.round(desde[1] + dy * avance);
  const haciaX = dx < 0;

  return (
    <g aria-hidden="true">
      <path d={lineaPixel(desde[0], desde[1], hasta[0], hasta[1])} fill="#c4d0dd" />
      {avance > 0.9 && (
        <path d={rectanguloPixel(hasta[0] - 5, hasta[1] - 5, 11, 11)} fill={color} opacity={0.3} />
      )}
      <path d={rectanguloPixel(hasta[0] - 3, hasta[1] - 3, 7, 7)} fill={`${color}`} opacity={0.16} />
      <g transform={`translate(${px},${py})`}>
        <rect x={-3} y={-3} width={7} height={7} fill="#ffffff" opacity={0.5} />
        <path d={rectanguloPixel(-1, -1, 3, 3)} fill={color} />
        <rect x={-1} y={-1} width={3} height={3} className={suave ? "" : "blink"} fill="none" stroke={color} />
      </g>
      <path
        d={lineaPixel(
          hasta[0] + (haciaX ? 4 : -4),
          hasta[1],
          hasta[0] + (haciaX ? 1 : -1),
          hasta[1],
        )}
        fill={`${color}`}
        opacity={0.5}
      />
    </g>
  );
}

/* -------------------------------------------------------------------- mesa */
function MesaCentral({
  txs,
  cadena,
  nuc,
  suave,
}: {
  txs: Tx[];
  cadena: string;
  nuc: { x: number; y: number; r: number };
  suave: boolean;
}) {
  const { x, y, r } = nuc;
  return (
    <g transform={`translate(${Math.round(x)},${Math.round(y)})`}>
      {/* anillo de energía que gira alrededor del núcleo */}
      {!suave && (
        <g opacity={0.55}>
          <rect
            x={-(r + 12)}
            y={-((r + 12) * 0.5) + 4}
            width={2 * (r + 12)}
            height={r + 12}
            fill="none"
            stroke="#6f9bff"
            strokeWidth={2}
            strokeDasharray="10 6"
          >
            <animateTransform
              attributeName="transform"
              type="rotate"
              from="0 0 0"
              to="360 0 0"
              dur="36s"
              repeatCount="indefinite"
            />
          </rect>
          <rect
            x={-(r + 14)}
            y={-((r + 14) * 0.5) + 5}
            width={2 * (r + 14)}
            height={r + 14}
            fill="none"
            stroke="#94a3b8"
            strokeWidth={1}
            strokeDasharray="4 18"
          >
            <animateTransform
              attributeName="transform"
              type="rotate"
              from="360 0 0"
              to="0 0 0"
              dur="48s"
              repeatCount="indefinite"
            />
          </rect>
        </g>
      )}
      {/* cúpula de luz que respira */}
      <circle cx={0} cy={0} r={r * 0.62} fill="url(#nucleoLuz)">
        {suave ? null : (
          <animate attributeName="opacity" values="0.5;1;0.5" dur="4s" repeatCount="indefinite" />
        )}
      </circle>

      {/* sombra en el suelo, a píxeles */}
      <path d={romboPixel(0, 16, r + 12, (r + 12) * 0.5)} fill="#64748b" opacity={0.1} />
      <path d={romboPixel(0, 11, r + 9, (r + 9) * 0.5)} fill="#64748b" opacity={0.14} />

      {/* tablero de la mesa con canto de madera */}
      <path d={romboPixel(0, 13, r + 7, (r + 7) * 0.5)} fill="#a9713c" />
      <path d={romboPixel(0, 10, r + 4, (r + 4) * 0.5)} fill="#c68a4c" />
      <path d={romboPixel(0, 0, r, r * 0.5)} fill="#f2f6fa" />
      <path d={romboPixel(0, 0, r, r * 0.5)} fill="none" stroke="#8b5a2b" strokeWidth={1} />
      <path d={romboPixel(0, 0, r - 5, (r - 5) * 0.5)} fill="#ffffff" />

      {/* la superficie de proyección de la mesa: aquí vive el grafo */}
      <path d={romboPixel(0, 0, r - 12, (r - 12) * 0.5)} fill="#f8fbfe" />
      {/* veta de la mesa y objetos en las esquinas, que si no parece una losa */}
      <path d={lineaPixel(-r + 16, -4, r - 16, -4)} fill="#e7eef6" />
      <path d={lineaPixel(-r + 26, 2, r - 26, 2)} fill="#e7eef6" />
      <g>
        <path d={rectanguloPixel(-r * 0.76, -r * 0.22, 7, 6)} fill="#6f9bff" />
        <path d={rectanguloPixel(-r * 0.76, -r * 0.22, 7, 2)} fill="#b9d0f7" />
        <path d={rectanguloPixel(r * 0.62, r * 0.1, 9, 6)} fill="#b45309" />
        <path d={rectanguloPixel(r * 0.62, r * 0.1, 9, 2)} fill="#d97706" />
      </g>
      <g transform={`translate(${-r},${-r * 0.8})`}>
        <PixelGraph txs={txs} cadena={cadena} ancho={r * 2} alto={r * 1.6} />
      </g>

      {/* patas y botonera */}
      <path d={rectanguloPixel(-r - 5, r * 0.4, 9, 5)} fill="#8b5a2b" />
      <path d={rectanguloPixel(r - 4, r * 0.4, 9, 5)} fill="#8b5a2b" />
      <path d={rectanguloPixel(-3, r * 0.46, 6, 4)} fill="#6f9bff">
        {suave ? null : (
          <animate attributeName="opacity" values="1;0.15;1" dur="1.8s" repeatCount="indefinite" />
        )}
      </path>
    </g>
  );
}

/** Onda del monitor: 14 columnas cuya altura depende de la carga del agente y
 *  de su semilla, para que dos agentes no dibujen la misma gráfica. */
function onda(carga: number, semilla: number): string {
  let d = "";
  for (let i = 0; i < 14; i++) {
    const v = Math.abs(Math.sin((i + semilla * 3.1) * 1.7 + carga * 6));
    const alto = 1 + Math.round(v * 3 * (0.4 + carga));
    d += rectanguloPixel(-8 + i, 4 - alto, 1, alto);
  }
  return d;
}

/* ------------------------------------------------------------------ puesto */
/* El puesto no rota: en una vista isométrica el mobiliario se dibuja siempre
   con la misma orientación (monitor arriba, silla abajo) y lo único que cambia
   es hacia dónde mira el agente. Rotarlo dejaba los rótulos del revés. */
function PuestoMesa({
  p,
  color,
  alarma,
  carga,
  nuc,
  suave,
}: {
  p: Puesto;
  color: string;
  alarma: boolean;
  carga: number;
  nuc: { x: number; y: number; r: number };
  suave: boolean;
}) {
  const anchoBarra = Math.max(4, Math.round(16 * Math.min(1, Math.max(0, carga))));
  // el rotulo se pone siempre hacia fuera de la mesa: si no, los de los
  // puestos laterales se montaban encima de la mesa central
  const dx = p.x - nuc.x;
  const dy = p.y - nuc.y;
  const ly = dy < 0 ? -46 : 26;
  const detalle = ORDEN.indexOf(p.id);
  return (
    <g transform={`translate(${p.x},${p.y})`} aria-hidden="true">
      {/* sombra del escritorio */}
      <path d={romboPixel(0, 14, 32, 16)} fill="#64748b" opacity={0.12} />

      {/* tablero de madera, cálido contra el suelo frío */}
      <path d={romboPixel(0, 10, 30, 15)} fill="#a9713c" />
      <path d={romboPixel(0, 0, 30, 15)} fill="#e2b27d" />
      <path d={romboPixel(0, 0, 30, 15)} fill="none" stroke="#8b5a2b" strokeWidth={1} />
      <path d={romboPixel(0, 0, 24, 12)} fill="#f0d3ab" />
      <path d={lineaPixel(-22, 0, 22, 0)} fill="#d9a469" opacity={0.7} />
      <path d={lineaPixel(-16, 4, 16, 4)} fill="#d9a469" opacity={0.5} />

      {/* cajonera, taza y papeles */}
      <path d={rectanguloPixel(-26, -3, 6, 9)} fill="#c68a4c" />
      <path d={rectanguloPixel(-25, -1, 4, 2)} fill="#f0d3ab" />
      <path d={rectanguloPixel(-25, 3, 4, 2)} fill="#f0d3ab" />
      <path d={rectanguloPixel(17, -6, 5, 5)} fill="#ffffff" />
      <path d={rectanguloPixel(18, -5, 3, 1)} fill="#94a3b8" />
      <path d={rectanguloPixel(-16, 6, 7, 4)} fill="#ffffff" opacity={0.85} />
      <path d={rectanguloPixel(-15, 7, 4, 1)} fill="#b6c4d6" />

      {/* patas */}
      <path d={rectanguloPixel(-19, 7, 3, 7)} fill="#8b5a2b" />
      <path d={rectanguloPixel(16, 7, 3, 7)} fill="#8b5a2b" />

      {/* teclado pixel sobre el tablero: cuadraditos de teclas */}
      <path d={rectanguloPixel(-11, -10, 22, 8)} fill="#f8fafc" />
      {[0, 1, 2, 3].map(c => (
        <path
          key={c}
          d={rectanguloPixel(-10 + c * 4, -9, 3, 2)}
          fill={alarma ? "#fca5a5" : color}
          opacity={0.9}
        />
      ))}
      <path d={rectanguloPixel(-11, -6, 22, 4)} fill="#dbe2ea" opacity={0.7} />

      {/* procesador: un ventilador de píxeles que gira */}
      <g transform="translate(13,6)">
        <path d={rectanguloPixel(-4, -4, 8, 8)} fill="#cbd5e1" />
        <path d={rectanguloPixel(-3, -3, 6, 6)} fill="#e2e8f0" />
        <path d={rectanguloPixel(-1, -1, 2, 2)} fill={alarma ? "#dc2626" : color} className={suave ? "" : "spin"}>
          {!suave && (
            <animate
              attributeName="transform"
              type="rotate"
              from="0 0 0"
              to="360 0 0"
              dur={p.ritmo.toFixed(2)}
              repeatCount="indefinite"
            />
          )}
        </path>
      </g>

      {/* cada escritorio tiene su cosa: no son siete mesas clonadas */}
      {detalle === 0 && (
        <>
          <path d={rectanguloPixel(14, -30, 13, 15)} fill="#8b5a2b" />
          <path d={rectanguloPixel(15, -29, 11, 13)} fill="#e2e8f0" />
          <path d={rectanguloPixel(16, -27, 9, 9)} fill={color} opacity={0.75} />
        </>
      )}
      {detalle === 1 && (
        <>
          <path d={rectanguloPixel(-30, -8, 6, 2)} fill="#92400e" />
          <path d={rectanguloPixel(-29, -7, 4, 6)} fill="#b45309" />
          <path d={rectanguloPixel(-28, -14, 2, 8)} fill="#15803d" />
          <path d={rectanguloPixel(-30, -12, 3, 3)} fill="#22c55e" />
        </>
      )}
      {detalle === 2 && (
        <>
          <path d={rectanguloPixel(16, 2, 10, 4)} fill="#ffffff" />
          <path d={rectanguloPixel(15, 5, 12, 3)} fill="#f1f5f9" />
          <path d={rectanguloPixel(17, 3, 6, 1)} fill="#b6c4d6" />
        </>
      )}
      {detalle === 3 && (
        <>
          <path d={rectanguloPixel(19, -8, 7, 7)} fill={alarma ? "#dc2626" : color} />
          <path d={rectanguloPixel(20, -7, 5, 5)} fill="#ffffff" opacity={0.5} />
        </>
      )}
      {detalle === 4 && (
        <>
          <path d={rectanguloPixel(-32, 2, 9, 5)} fill="#ffffff" />
          <path d={rectanguloPixel(-31, 3, 5, 1)} fill="#94a3b8" />
        </>
      )}
      {detalle === 5 && (
        <>
          <path d={rectanguloPixel(16, -4, 8, 5)} fill="#a9713c" />
          <path d={rectanguloPixel(17, -6, 6, 2)} fill="#c68a4c" />
        </>
      )}
      {detalle === 6 && (
        <>
          <path d={rectanguloPixel(-33, -10, 8, 8)} fill="#e2e8f0" />
          <path d={rectanguloPixel(-32, -9, 6, 2)} fill={color} />
          <path d={rectanguloPixel(-32, -6, 4, 2)} fill="#94a3b8" />
        </>
      )}

      {/* el monitor enseña una onda que se mueve con la carga del agente */}
      <path d={onda(carga, detalle)} fill={alarma ? "#fca5a5" : color} opacity={0.85} />

      {/* aviso flotante cuando el agente esta en alerta */}
      {alarma && !suave && (
        <g>
          <path d={rectanguloPixel(-5, -62, 12, 10)} fill="#b9c6d6" />
          <path d={rectanguloPixel(-6, -63, 12, 10)} fill="#ffffff" />
          <path d={rectanguloPixel(-2, -52, 4, 3)} fill="#ffffff" />
          <path d={rectanguloPixel(-1, -61, 2, 4)} fill="#dc2626" />
          <path d={rectanguloPixel(-1, -56, 2, 2)} fill="#dc2626" />
          <animateTransform
            attributeName="transform"
            type="translate"
            values="0 0; 0 -3; 0 0"
            dur="1.3s"
            repeatCount="indefinite"
          />
        </g>
      )}

      <g transform="translate(0,-19)">
        <path d={rectanguloPixel(-13, -15, 26, 19)} fill="#8b5a2b" />
        <path d={rectanguloPixel(-12, -14, 24, 17)} fill="#e2e8f0" />
        <path d={rectanguloPixel(-10, -12, 20, 13)} fill={alarma ? "#7f1d1d" : "#0f172a"} />
        <path d={rectanguloPixel(-8, -10, anchoBarra, 2)} fill={alarma ? "#fca5a5" : color} />
        <path d={rectanguloPixel(-8, -6, Math.round(anchoBarra * 0.6), 2)} fill="#64748b" />
        <path d={rectanguloPixel(-8, -2, 11, 2)} fill="#475569" />
        {!suave && (
          <path d={rectanguloPixel(-8, 0, 7, 2)} fill={alarma ? "#dc2626" : color} className="blink">
            <animate
              attributeName="opacity"
              values="1;0.1;1"
              dur={`${p.ritmo.toFixed(2)}s`}
              repeatCount="indefinite"
            />
          </path>
        )}
        <path d={rectanguloPixel(-2, 3, 4, 4)} fill="#94a3b8" />
      </g>

      <path
        d={rectanguloPixel(18, -4, 4, 4)}
        fill={alarma ? "#dc2626" : color}
        className={alarma ? "blink" : ""}
      />
      <g transform={`translate(0,${ly})`}>
        <path d={rectanguloPixel(-19, 0, 38, 9)} fill="#ffffff" opacity={0.94} />
        <path d={rectanguloPixel(-19, 0, 38, 9)} fill="none" stroke={color} strokeWidth={0.5} />
        <text y={7} textAnchor="middle" className="floor-station-name">
          {p.id}
        </text>
      </g>
    </g>
  );
}

/* ------------------------------------------------------------------- robot */
function Robot({
  p,
  color,
  carga,
  alarma,
  escala,
  suave,
}: {
  p: Puesto;
  color: string;
  carga: number;
  alarma: boolean;
  escala: number;
  suave: boolean;
}) {
  const t = useFrame();
  const dur = p.periodo * (1.2 - Math.min(1, Math.max(0, carga)) * 0.45);
  const c = suave ? 0 : faseEnCiclo(t, dur, p.fase);
  // en alerta el agente deja lo que estuviera haciendo: se pone nervioso
  const modo: Postura = alarma ? "alert" : suave ? "type" : modoEnCiclo(c);
  const pose = posicionEnCiclo(c, p.ruta as [[number, number], [number, number], [number, number]]);
  const mirando = pose.dx !== 0 ? pose.dx < 0 : p.ruta[2][0] < 0;

  return (
    <g
      transform={`translate(${p.x + Math.round(pose.x)},${p.y + Math.round(pose.y) + DESPLAZE - 16 * escala})`}
      aria-hidden="true"
    >
      {/* sombra bajo los pies */}
      <path
        d={romboPixel(escala * 5, 16 * escala - escala, escala * 4, escala * 2)}
        fill="#334155"
        opacity={0.18}
      />
      {modo === "walk" && (
        <path d={rectanguloPixel(-4, -11 * escala, 3, 3)} fill={color} opacity={0.9} />
      )}
      {modo === "carry" && (
        <path
          d={rectanguloPixel(6 * escala - 2, 9 * escala, 3, 3)}
          fill={color}
          opacity={0.95}
        />
      )}
      <AgentePixel
        id={p.id}
        color={color}
        escala={escala}
        flip={mirando}
        modo={modo}
        alerta={alarma}
        frameBase={Math.round(p.fase * 4)}
      />
    </g>
  );
}
