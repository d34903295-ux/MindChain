"use client";

/**
 * Motor de pixel art.
 *
 * Un sprite es una rejilla de caracteres: cada carácter es un píxel y cada
 * carácter distinto es un color. Se dibujan así porque es exactamente como
 * se hacía a mano (o con Aseprite) y, sobre todo, porque así los píxeles son
 * cuadrados de verdad y no curvas suavizadas.
 *
 * Cuatro decisiones que hacen que esto no se arrastre:
 *
 * 1. Cada frame se compila a UNA ruta por color, no un <rect> por píxel. Un
 *    sprite de 12×16 son 192 píxeles; como rects serían 192 nodos por robot.
 *    Con rutas son 3-4 nodos.
 * 2. Un único reloj global (useFrame) mueve todos los robots. Siete
 *    setIntervalserían siete timers compitiendo por el hilo principal.
 * 3. `shape-rendering="crispEdges"` desactiva el suavizado: sin esto el
 *    navegador dibuja los bordes redondeados y se pierde el efecto.
 * 4. El contorno (`contornear`) se compila en el espacio del sprite, no en
 *    píxeles de pantalla: por eso un solo pixel de borde sirve escalado y
 *    volteado sin volver a calcular nada.
 */
import { useEffect, useState } from "react";

export type Pixel = string;
export type Frame = Pixel[];
export type Sprite = Frame[];
export type Paleta = Record<string, string>;

/** Una capa dibujable: un color y su ruta. Un frame son sus capas, de fondo a frente. */
export type Capa = { color: string; d: string };
export type FrameCompilado = Capa[];
export type SpriteCompilado = FrameCompilado[];

const TRANSPARENT = ".";
/** Si la paleta no trae clave de contorno, este oscuro funciona igual que sobre madera. */
const OUTLINE_FALLBACK = "#0f172a";
/** Claves que se toman como "el color del contorno" si nadie lo pasa explícito. */
const CLAVES_CONTORNO = ["o", "outline", "contorno", "k"];

/** Convierte un frame en una ruta por color. */
export function compilar(frame: Frame, paleta: Paleta): FrameCompilado {
  const porColor = new Map<string, string[]>();
  for (let y = 0; y < frame.length; y++) {
    const fila = frame[y];
    // `for..of` recorre los mismos puntos de código que `[...fila]`, pero sin
    // copiar la fila en un array ni crear una closure por fila.
    let x = -1;
    for (const ch of fila) {
      x += 1;
      if (ch === TRANSPARENT) continue;
      const color = paleta[ch];
      if (!color) continue;
      const partes = porColor.get(color);
      if (partes) partes.push(`M${x} ${y}h1v1h-1z`);
      else porColor.set(color, [`M${x} ${y}h1v1h-1z`]);
    }
  }
  const capas: FrameCompilado = [];
  porColor.forEach((partes, color) => capas.push({ color, d: partes.join("") }));
  return capas;
}

export function compilarSprite(sprite: Sprite, paleta: Paleta): SpriteCompilado {
  return sprite.map(f => compilar(f, paleta));
}

/* ── contorno ──────────────────────────────────────────────────────────── */

export interface OpcionesContorno {
  /** Color del borde. Por defecto, la primera clave de CLAVES_CONTORNO que exista. */
  color?: string;
  /** Grosor del anillo, en píxeles de sprite (solo modo "contorno"). */
  grosor?: 1 | 2;
  /** "contorno" rodea la silueta; "sombra" la desplaza y la deja detrás. */
  modo?: "contorno" | "sombra";
  /** Desplazamiento de la sombra, en píxeles de sprite. */
  desplazamiento?: [number, number];
}

function colorDeContorno(paleta?: Paleta): string {
  if (paleta) {
    for (const clave of CLAVES_CONTORNO) {
      const v = paleta[clave];
      if (v) return v;
    }
  }
  return OUTLINE_FALLBACK;
}

/** Píxeles cubiertos por un frame, como máscara booleana sobre su caja envolvente. */
type Mascara = { m: Uint8Array; x0: number; y0: number; ancho: number; alto: number };

function mascaraDe(frame: FrameCompilado): Mascara | null {
  // Solo troceamos el formato que emite compilar(): un rect de 1 px por subruta.
  const trozo = /M(-?\d+) (-?\d+)h1v1h-1z/g;
  const puntos: number[] = [];
  let x0 = Infinity;
  let y0 = Infinity;
  let x1 = -Infinity;
  let y1 = -Infinity;
  for (const capa of frame) {
    trozo.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = trozo.exec(capa.d)) !== null) {
      const x = +m[1];
      const y = +m[2];
      puntos.push(x, y);
      if (x < x0) x0 = x;
      if (x > x1) x1 = x;
      if (y < y0) y0 = y;
      if (y > y1) y1 = y;
    }
  }
  if (x1 < x0) return null;
  const ancho = x1 - x0 + 1;
  const alto = y1 - y0 + 1;
  const m = new Uint8Array(ancho * alto);
  for (let i = 0; i < puntos.length; i += 2) {
    m[(puntos[i + 1] - y0) * ancho + (puntos[i] - x0)] = 1;
  }
  return { m, x0, y0, ancho, alto };
}

/** Borra del destino los píxeles del cuerpo: el halo nunca se pisa a sí mismo. */
function sinSilueta(destino: Mascara, silueta: Mascara, dx: number, dy: number) {
  const { m, ancho, alto } = silueta;
  for (let y = 0; y < alto; y++) {
    for (let x = 0; x < ancho; x++) {
      if (m[y * ancho + x] === 0) continue;
      destino.m[(y + dy) * destino.ancho + (x + dx)] = 0;
    }
  }
}

/** Anillo de `grosor` píxeles alrededor del cuerpo. */
function dilatar(s: Mascara, grosor: number): Mascara {
  const { m, x0, y0, ancho, alto } = s;
  const nw = ancho + grosor * 2;
  const nh = alto + grosor * 2;
  const out: Mascara = { m: new Uint8Array(nw * nh), x0: x0 - grosor, y0: y0 - grosor, ancho: nw, alto: nh };
  for (let y = 0; y < alto; y++) {
    for (let x = 0; x < ancho; x++) {
      if (m[y * ancho + x] === 0) continue;
      const ox = x + grosor;
      const oy = y + grosor;
      const xA = Math.max(0, ox - grosor);
      const xB = Math.min(nw - 1, ox + grosor);
      const yA = Math.max(0, oy - grosor);
      const yB = Math.min(nh - 1, oy + grosor);
      for (let ny = yA; ny <= yB; ny++) {
        const fila = ny * nw;
        for (let nx = xA; nx <= xB; nx++) out.m[fila + nx] = 1;
      }
    }
  }
  sinSilueta(out, s, grosor, grosor);
  return out;
}

/** La silueta corrida dx,dy. Detrás del cuerpo hace de sombra. */
function desplazar(s: Mascara, dx: number, dy: number): Mascara {
  const { m, x0, y0, ancho, alto } = s;
  const px = dx >= 0 ? 0 : -dx;
  const py = dy >= 0 ? 0 : -dy;
  const nw = ancho + Math.abs(dx);
  const nh = alto + Math.abs(dy);
  const out: Mascara = { m: new Uint8Array(nw * nh), x0: x0 - px, y0: y0 - py, ancho: nw, alto: nh };
  for (let y = 0; y < alto; y++) {
    for (let x = 0; x < ancho; x++) {
      if (m[y * ancho + x] === 0) continue;
      out.m[(y + py + dy) * nw + (x + px + dx)] = 1;
    }
  }
  sinSilueta(out, s, px, py);
  return out;
}

/** Serializa una máscara. Pixels contiguos en la misma fila salen como un solo `h`. */
function mascaraAPath({ m, x0, y0, ancho, alto }: Mascara): string {
  const partes: string[] = [];
  for (let y = 0; y < alto; y++) {
    const fila = y * ancho;
    let x = 0;
    while (x < ancho) {
      if (m[fila + x] === 0) {
        x += 1;
        continue;
      }
      let largo = 1;
      while (x + largo < ancho && m[fila + x + largo] === 1) largo += 1;
      partes.push(`M${x + x0} ${y + y0}h${largo}v1h${-largo}z`);
      x += largo;
    }
  }
  return partes.join("");
}

/**
 * Devuelve los mismos frames con una capa de borde detrás de las normales.
 * Trabaja en el espacio del sprite (0-11 x 0-15), así que el resultado lo
 * dibuja PixelSprite con su propia escala y su flip sin tocar nada más.
 */
export function contornear(
  frames: SpriteCompilado,
  paleta?: Paleta,
  opciones: OpcionesContorno = {},
): SpriteCompilado {
  const color = opciones.color ?? colorDeContorno(paleta);
  const grosor = opciones.grosor ?? 1;
  const modo = opciones.modo ?? "contorno";
  const [dx, dy] = opciones.desplazamiento ?? (modo === "sombra" ? [1, 1] : [0, 0]);
  return frames.map(frame => {
    const silueta = mascaraDe(frame);
    if (!silueta) return frame;
    const d = mascaraAPath(modo === "sombra" ? desplazar(silueta, dx, dy) : dilatar(silueta, grosor));
    if (!d) return frame;
    const salida = frame.slice();
    // Una ruta por color: si el sprite ya usa ese color, se le pega el borde en
    // vez de crear un nodo nuevo. El borde no pisa el cuerpo, así que da igual
    // en qué capa quede.
    const i = salida.findIndex(capa => capa.color === color);
    if (i < 0) salida.unshift({ color, d });
    else salida[i] = { color, d: salida[i].d + d };
    return salida;
  });
}

/**
 * Los frames compilados no se tocan nunca, así que el resultado del borde se
 * cachea por identidad del array + opciones. Sin esto serían ~200 píxeles de
 * máscara por agente y frame, y PixelSprite se repinta a 60 fps.
 */
const cacheBorde = new WeakMap<SpriteCompilado, Map<string, SpriteCompilado>>();

function framesConBorde(frames: SpriteCompilado, paleta: Paleta, opciones: OpcionesContorno) {
  const color = opciones.color ?? colorDeContorno(paleta);
  const modo = opciones.modo ?? "contorno";
  const grosor = opciones.grosor ?? 1;
  const desp = opciones.desplazamiento;
  const clave = `${color}|${modo}|${grosor}|${desp ? desp[0] + "," + desp[1] : ""}`;
  let porClave = cacheBorde.get(frames);
  if (!porClave) {
    porClave = new Map();
    cacheBorde.set(frames, porClave);
  }
  let v = porClave.get(clave);
  if (!v) {
    v = contornear(frames, paleta, { ...opciones, color });
    porClave.set(clave, v);
  }
  return v;
}

/**
 * Reloj global. Un solo `requestAnimationFrame` para toda la sala: cada
 * consumidor lee el mismo contador y decide su frame.
 */
let tickGlobal = 0;
const suscriptores = new Set<(t: number) => void>();
let rafId: number | null = null;

function arrancar() {
  if (rafId !== null || typeof window === "undefined") return;
  const paso = () => {
    tickGlobal += 1;
    suscriptores.forEach(fn => fn(tickGlobal));
    rafId = requestAnimationFrame(paso);
  };
  rafId = requestAnimationFrame(paso);
}

/** Sin suscriptores el reloj no tiene a quién avisar, así que se apaga: antes
 *  seguía pidiendo frames para siempre. */
function detener() {
  if (rafId === null) return;
  cancelAnimationFrame(rafId);
  rafId = null;
}

export function useFrame() {
  const [t, setT] = useState(tickGlobal);
  useEffect(() => {
    suscriptores.add(setT);
    arrancar();
    return () => {
      suscriptores.delete(setT);
      if (suscriptores.size === 0) detener();
    };
  }, []);
  return t;
}

/** Dibuja un sprite eligiendo el frame según el reloj. */
export function PixelSprite({
  frames,
  paleta,
  escala = 1,
  flip = false,
  frame = 0,
  className,
  contorno = false,
  sombra,
  colorContorno,
  grosor = 1,
}: {
  frames: ReturnType<typeof compilarSprite>;
  paleta: Paleta;
  escala?: number;
  flip?: boolean;
  frame?: number;
  className?: string;
  /** Anillo de 1 px detrás del sprite: es lo que lo despega del fondo. */
  contorno?: boolean;
  /** Silueta desplazada 1 o 2 px detrás, en vez de anillo. */
  sombra?: 1 | 2;
  /** Color del borde; por defecto se busca en la paleta. */
  colorContorno?: string;
  /** Grosor del anillo; solo aplica a `contorno`. */
  grosor?: 1 | 2;
}) {
  const capas =
    contorno || sombra !== undefined
      ? framesConBorde(frames, paleta, {
          color: colorContorno,
          grosor,
          modo: sombra !== undefined ? "sombra" : "contorno",
          desplazamiento: sombra !== undefined ? [sombra, sombra] : undefined,
        })
      : frames;
  const f = capas[((frame % capas.length) + capas.length) % capas.length];
  return (
    <g transform={`scale(${flip ? -escala : escala} ${escala})`} className={className} aria-hidden="true">
      {f.map((capa, i) => (
        <path key={i} d={capa.d} fill={capa.color} />
      ))}
    </g>
  );
}

/** Rompe una línea en peldaños: así las aristas también son de píxeles. */
export function lineaPixel(x1: number, y1: number, x2: number, y2: number): string {
  const pasos = Math.max(Math.abs(x2 - x1), Math.abs(y2 - y1), 1);
  const partes: string[] = [];
  let x = Math.round(x1);
  let y = Math.round(y1);
  const ex = Math.round(x2);
  const ey = Math.round(y2);
  partes.push(`M${x} ${y}h1v1h-1z`);
  for (let i = 1; i <= pasos; i++) {
    const nx = Math.round(x1 + ((x2 - x1) * i) / pasos);
    const ny = Math.round(y1 + ((y2 - y1) * i) / pasos);
    if (nx !== x || ny !== y) {
      partes.push(`M${nx} ${ny}h1v1h-1z`);
      x = nx;
      y = ny;
    }
  }
  void ex;
  void ey;
  return partes.join("");
}

/** Rompe una elipse (los azulejos isométricos) en píxeles. */
export function romboPixel(cx: number, cy: number, rx: number, ry: number): string {
  const partes: string[] = [];
  for (let y = Math.floor(cy - ry); y <= Math.ceil(cy + ry); y++) {
    const t = (y - (cy - ry)) / (ry * 2 || 1);
    if (t < 0 || t > 1) continue;
    const ancho = Math.round(rx * 2 * (1 - Math.abs(t - 0.5) * 2));
    if (ancho <= 0) continue;
    const x = Math.round(cx - ancho / 2);
    partes.push(`M${x} ${y}h${ancho}v1h${-ancho}z`);
  }
  return partes.join("");
}

export function rectanguloPixel(x: number, y: number, w: number, h: number): string {
  return `M${Math.round(x)} ${Math.round(y)}h${Math.round(w)}v${Math.round(h)}h${-Math.round(w)}z`;
}

/** Rompe un círculo en píxeles (nodos, focos). */
export function circuloPixel(cx: number, cy: number, r: number): string {
  const partes: string[] = [];
  const paso = Math.max(1, Math.ceil(r / 2));
  for (let y = -r; y <= r; y += paso) {
    for (let x = -r; x <= r; x += paso) {
      if (x * x + y * y <= r * r) partes.push(`M${cx + x} ${cy + y}h1v1h-1z`);
    }
  }
  return partes.join("");
}

/* ── tramado ───────────────────────────────────────────────────────────── */

/** El suelo repite los mismos tramados en cada render; 256 entradas es de sobra. */
const cacheTrama = new Map<string, string>();

/**
 * Píxeles alternados dentro de un rectángulo: sirve para sombras suaves (con
 * `opacity` baja) y para que un suelo grande no quede plano.
 * Determinista: `fase` sólo desplaza el patrón, así que el mismo rectángulo
 * devuelve siempre la misma ruta y se puede cachear. `densidad` 2 es el
 * ajedrezado al 50 %, 3 deja un píxel de cada tres.
 */
export function ditherRect(x: number, y: number, w: number, h: number, fase = 0, densidad = 2): string {
  const x0 = Math.round(x);
  const y0 = Math.round(y);
  const w0 = Math.round(w);
  const h0 = Math.round(h);
  const p0 = Math.round(fase);
  const salto = Math.max(1, Math.round(densidad));
  if (w0 <= 0 || h0 <= 0) return "";
  const clave = `${x0},${y0},${w0},${h0},${p0},${salto}`;
  const hit = cacheTrama.get(clave);
  if (hit !== undefined) return hit;
  const m = new Uint8Array(w0 * h0);
  for (let py = 0; py < h0; py++) {
    const fila = py * w0;
    for (let px = 0; px < w0; px++) {
      if ((((x0 + px + y0 + py + p0) % salto) + salto) % salto === 0) m[fila + px] = 1;
    }
  }
  const out = mascaraAPath({ m, x0, y0, ancho: w0, alto: h0 });
  if (cacheTrama.size >= 256) cacheTrama.clear();
  cacheTrama.set(clave, out);
  return out;
}
