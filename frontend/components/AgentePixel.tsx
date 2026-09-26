"use client";

import { compilarSprite, PixelSprite, useFrame, type Paleta } from "./pixel";
import { ESTILO, SPRITES, type Postura } from "./sprites";
import type { AgenteId } from "./AgentPixel";

const P: Paleta = {
  o: "#2b3a52", // contorno
  w: "#ffffff", // casco claro
  g: "#e2e8f0", // cuerpo medio
  d: "#b6c4d6", // sombra
  v: "#0f172a", // visor
  s: "#94a3b8", // sombra del color del agente
  l: "#f8fafc", // luz del color del agente
};

/** Mezcla un color con blanco (k>0) o con negro (k<0). Sirve para sacar la
 *  luz y la sombra de cada agente sin escribir dos paletas. */
export function mezclar(hex: string, k: number): string {
  const n = parseInt(hex.slice(1), 16);
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  const t = k < 0 ? 0 : 255;
  const p = Math.abs(k);
  const m = (c: number) => Math.round(c + (t - c) * p);
  return `#${((1 << 24) + (m(r) << 16) + (m(g) << 8) + m(b)).toString(16).slice(1)}`;
}

export type { AgenteId };
export type { Postura };

/** Falla en desarrollo si un sprite no encaja: datos a mano se descuadran. */
function checkSprite(nombre: string, id: AgenteId, estado: Postura) {
  if (typeof window === "undefined" || process.env.NODE_ENV === "production") return;
  const frames = SPRITES[id][estado] ?? SPRITES[id].idle;
  frames.forEach((f, i) => {
    if (f.length !== 16) {
      // eslint-disable-next-line no-console
      console.error(`sprite ${nombre} frame ${i}: ${f.length} filas, se esperaban 16`);
    }
    f.forEach((fila, y) => {
      if (fila.length !== 12) {
        // eslint-disable-next-line no-console
        console.error(`sprite ${nombre} frame ${i} fila ${y}: ${fila.length} columnas ("${fila}")`);
      }
    });
  });
}

const cache = new Map<string, ReturnType<typeof compilarSprite>>();
function spriteDe(id: AgenteId, estado: Postura) {
  const clave = `${id}:${estado}`;
  let v = cache.get(clave);
  if (!v) {
    const frames = SPRITES[id][estado] ?? SPRITES[id].idle;
    checkSprite(clave, id, estado);
    v = compilarSprite(frames, P);
    cache.set(clave, v);
  }
  return v;
}

/**
 * Agente pixel-art con animación.
 * `modo` lo decide la ronda: teclea en su puesto, camina a la mesa, saluda al
 * llegar y vuelve cargando el paquete. `frameBase` desincroniza a los siete.
 */
export function AgentePixel({
  id,
  color,
  escala = 3,
  flip = false,
  modo = "type",
  alerta = false,
  frameBase = 0,
  contorno = false,
}: {
  id: AgenteId;
  color: string;
  escala?: number;
  flip?: boolean;
  modo?: Postura;
  alerta?: boolean;
  frameBase?: number;
  /** Una capa de 1 px detras: separa al robot del suelo claro y de la madera. */
  contorno?: boolean;
}) {
  const t = useFrame();
  // el acento 'e' es el color puro del agente; 's' y 'l' son su sombra y su
  // luz, y son los que dan volumen al cuerpo en vez de un color plano
  const paleta: Paleta = {
    ...P,
    c: color,
    e: alerta ? "#ffffff" : color,
    s: mezclar(color, -0.3),
    l: mezclar(color, 0.32),
  };
  const estilo = ESTILO[id];
  const frames = spriteDe(id, modo);
  // cada gesto va a su ritmo y encima cada agente tiene el suyo
  const base = modo === "type" ? 4 : modo === "wave" ? 4 : 3;
  const divisor = Math.max(1, Math.round(base / estilo.ritmo));
  const frame = Math.floor(t / divisor) + frameBase;
  // en los frames de paso el cuerpo sube un píxel: el rebote del ciclo
  const enPaso = modo === "walk" || modo === "carry";
  // el rebote: el que va marcado pega mas fuerte que el que va de puntillas
  const rebote = enPaso && (Math.floor(t / divisor) & 1) === 1 ? -estilo.rebote : 0;
  // los nerviosos tiemblan: un pixel de lado cada dos frames
  const temblor = estilo.nervios && (Math.floor(t / 2) & 1) === 1 ? 1 : 0;
  return (
    <g transform={`translate(${flip ? -temblor : temblor},${rebote})`}>
      <PixelSprite
        contorno={contorno}
        frames={frames}
        paleta={paleta}
        escala={escala}
        flip={flip}
        frame={frame}
      />
    </g>
  );
}
