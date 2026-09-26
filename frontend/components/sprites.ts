import type { AgenteId } from "./AgentPixel";
import type { ModoAgente } from "./movimiento";
import type { Sprite } from "./pixel";

/**
 * Sprites de los agentes: 12×16 píxeles, dibujados a mano como en un juego.
 *
 * Cada agente tiene el mismo cuerpo —para que se lean como un equipo— pero
 * un accesorio distinto en la cabeza, ropa propia y, sobre todo, un estilo de
 * movimiento propio: no es que los siete caminen igual y se les cambie el color.
 *
 *   idle   → 2-3 frames respirando: solo el torso sube y baja un píxel
 *   walk   → 4 frames con SU marcha: zancada normal, marcha tying legs o
 *             de puntillas, y el balanceo de brazos que le corresponde
 *   type   → 4 frames con SU forma de teclear: a dos manos, a una mano
 *             (el que busca y pulscha), o despacio y sin apartar las manos
 *   wave   → 2 frames levantando el brazo derecho o el izquierdo, 3 si saluda
 *             con los dos
 *   carry  → 4 frames volviendo: con las dos manos, con una o con el bulto
 *             en el hombro
 *   alert  → 3 frames en alarma: el visor se le enciende a todos y cada uno
 *             reacciona a su manera (se tapa la cara, se yergue, retrocede)
 *
 * Cada agente además tiene su tempo (qué rápido teclea) y su nervios (si se le
 * ve temblar), para que dos que tecleen a la vez no se confundan.
 *
 * El cuerpo tiene volumen: 'l' es la luz del lado izquierdo, 's' la sombra
 * del derecho, 'c' el color del agente y 'e' su acento brillante.
 *
 * Los píxeles se compilan a rutas (ver pixel.tsx) para que 7 robots no cuesten
 * 1.300 nodos DOM.
 */

export const ANCHO = 12;
export const ALTO = 16;

export type Postura = ModoAgente | "idle" | "alert";

/* ------------------------------------------------------------------ cuerpo */
/* 12 columnas x 16 filas. Casco de 6 filas, torso 5 y piernas 4. */
const base: string[] = [
  "....oooo....",
  "...owwwwo...",
  "..olwwwwso..",
  "..ovleevvo..",
  "...owwwwo...",
  "...oooooo...",
  "..ollllllo..",
  ".occcccccco.",
  ".occcccccco.",
  ".occcwwccco.",
  "..occcccco..",
  "...oooooo...",
  "..oo....oo..",
  "..oo....oo..",
  "..oo....oo..",
  "..oo....oo..",
];

/** Cambia un píxel garantizando el ancho: el slice conserva la longitud. */
const parche = (fila: string, x: number, ch: string): string =>
  fila.slice(0, x) + ch + fila.slice(x + 1);

const con = (f: string[], y: number, fila: string): string[] => {
  const copia = f.slice();
  copia[y] = fila;
  return copia;
};

/** Varios píxeles de la misma fila, encadenados. */
const puntos = (f: string[], y: number, ...ps: [x: number, ch: string][]): string[] => {
  let fila = f[y];
  ps.forEach(([x, ch]) => {
    fila = parche(fila, x, ch);
  });
  return con(f, y, fila);
};

/* -------------------------------------------------------------- accesorios */
const ACCESORIO: Record<AgenteId, (f: string[]) => string[]> = {
  // gorra plana con visera a la derecha
  wallet: f => con(con(f, 0, "....cccc...."), 1, "...occcccco."),
  // la misma gorra, puesta del revés
  transaction: f => con(con(f, 0, "....cccc...."), 1, ".occcccco..."),
  // gafas: dos lentes separadas en el visor
  contract: f => con(f, 3, "..oveevevo.."),
  // antena con la punta encendida, cuerpo fino
  research: f =>
    con(con(con(con(f, 1, "...owwowo..."), 0, "......e....."), 7, "..occcccco.."), 8, "..occcccco.."),
  // auriculares con micro y hombreras anchas
  monitoring: f =>
    con(
      con(con(con(f, 1, ".solwwwwsos."), 2, ".solwwwwsos."), 3, "..ovveevvo.e"),
      7,
      ".soccccccos.",
    ),
  // cresta, cuello de pinchos y hombreras
  risk: f =>
    con(
      con(con(con(con(f, 0, ".....cc....."), 1, "....cccc...."), 6, "..oeweewoo.."), 7, ".soccccccos."),
      8,
      ".soccccccos.",
    ),
  // gorro con pompón
  explanation: f => con(con(f, 0, ".....ee....."), 1, "..occcccco.."),
};

export function cuerpoDe(id: AgenteId): string[] {
  return ROPA[id](ACCESORIO[id](base.slice()));
}

/* -------------------------------------------------------------------- ropa */
/* Detalles dentro del torso. Ninguno toca el contorno: de lejos la silueta se
   sigue leyendo igual que en el resto del equipo, y de cerca hay algo más que
   un maniquí de color. */
const ROPA: Record<AgenteId, (f: string[]) => string[]> = {
  // cinturón con hebilla y el bolsillo iluminado
  wallet: f => puntos(puntos(f, 11, [5, "e"], [6, "e"]), 9, [2, "l"]),
  // pañuelo al cuello y el bolsillo del lado de la sombra
  transaction: f => puntos(puntos(f, 6, [4, "c"], [7, "s"]), 9, [9, "d"]),
  // pañuelo en la cintura y hebilla
  contract: f => puntos(puntos(f, 10, [4, "w"]), 11, [6, "e"]),
  // tarjeta de identificación colgando del cuello, y bolsillo
  research: f => puntos(puntos(puntos(f, 6, [5, "c"]), 7, [5, "w"]), 10, [7, "d"]),
  // radio prendida en el pecho y cinturón
  monitoring: f => puntos(puntos(f, 8, [4, "w"]), 11, [5, "e"]),
  // correa cruzada y cartuchera en la cadera
  risk: f => puntos(puntos(f, 8, [3, "s"]), 10, [2, "s"]),
  // delantal claro y bolsillos de la cintura
  explanation: f => puntos(puntos(f, 7, [5, "w"], [6, "w"]), 10, [3, "d"], [8, "d"]),
};

/* ---------------------------------------------------------- torso y brazos */
/** Marcha: el brazo del lado que atrasa se alarga un píxel hacia abajo. */
const brazoAtrasIzq = (b: string[]): string[] =>
  con(con(b, 8, parche(parche(b[8], 0, "o"), 1, "o")), 9, parche(b[9], 1, "o"));

const brazoAtrasDer = (b: string[]): string[] =>
  con(con(b, 8, parche(parche(b[8], 11, "o"), 10, "o")), 9, parche(b[9], 10, "o"));

/** Cargar el bulto: las manos van al frente, al hombro o a un solo lado. */
const torsoCarga = (b: string[], modo: Carga): string[] => {
  const f = b.slice();
  if (modo === "hombro") {
    f[8] = parche(parche(f[8], 10, "o"), 9, "e");
    return f;
  }
  if (modo === "una") {
    f[8] = parche(f[8], 7, "o");
    f[9] = parche(f[9], 7, "o");
    return f;
  }
  f[8] = parche(parche(f[8], 4, "o"), 7, "o");
  f[9] = parche(parche(f[9], 4, "o"), 7, "o");
  return f;
};

export type Carga = "dos" | "una" | "hombro";

/* ------------------------------------------------------------------ piernas */
/* Cada pierna tiene cinco poses: apoyada (con pie), alzada (el pie no toca
   el suelo), de paso (vertical, bajo el cuerpo), corta (alzada y recogida,
   para andar de puntillas) y atrás (el pie rezagado, para el que retrocede).
   Son mitades de 6 columnas. */
const izq = {
  apoyada: ["..oo..", "..oo..", "..oo..", ".ooo.."],
  alzada: ["..oo..", "..oo..", "......", "......"],
  paso: ["...o..", "...o..", "...o..", "..oo.."],
  corta: ["...o..", "...o..", "......", "......"],
  atras: ["..oo..", "..oo..", ".oo...", ".ooo.."],
};
const der = {
  apoyada: ["..oo..", "..oo..", "..oo..", "..ooo."],
  alzada: ["..oo..", "..oo..", "......", "......"],
  paso: ["..o...", "..o...", "..o...", "..oo.."],
  corta: ["..o...", "..o...", "......", "......"],
  atras: ["..oo..", "..oo..", "...oo.", "..ooo."],
};

/** Une un torso (filas 0-11) con unas piernas (filas 12-15). */
const ensamblar = (torso: string[], piernaIzq: string[], piernaDer: string[]): string[] => {
  const out = torso.slice(0, 12);
  for (let i = 0; i < 4; i++) {
    const a = piernaIzq[i] ?? "......";
    const b = piernaDer[i] ?? "......";
    out.push(a.slice(0, 6) + b.slice(0, 6));
  }
  return out;
};

/* ------------------------------------------------------------------ manos */
// media fila cada una (6 columnas): izquierda y derecha, se concatenan.
const manos = {
  arriba: { izq: "..oo..", der: "..oo.." },
  abajo: { izq: ".ooo..", der: "..ooo." },
  medioI: { izq: ".ooo..", der: "..oo.." },
  medioD: { izq: "..oo..", der: ".ooo.." },
  flashI: { izq: ".oco..", der: "..oo.." },
  flashD: { izq: "..oo..", der: "..oco." },
  soloIzq: { izq: ".ooo..", der: "......" },
  soloDer: { izq: "......", der: "..ooo." },
  // puños cerrados, las dos manos delante de la cara y manos al cuello
  cerrado: { izq: ".ocoo.", der: ".ooco." },
  rostro: { izq: "..ooo.", der: ".ooo.." },
  cuello: { izq: ".oo...", der: "...oo." },
};

/** Teclear. `fila` es la del torso donde caen las manos (4 a 10): al pulsar
 *  la tecla el cuerpo baja un píxel. */
const tecleo = (b: string[], fila: number, a: string, c: string, bajo = 0): string[] => {
  const out: string[] = [];
  for (let y = 0; y < ALTO; y++) {
    if (y === 0 && bajo) {
      out.push("............");
      continue;
    }
    if (y + bajo === fila) {
      out.push(a.slice(0, 6) + c.slice(0, 6));
      continue;
    }
    out.push(b[y + bajo] ?? b[y] ?? "............");
  }
  return out;
};

export type Tecla = [fila: number, izq: string, der: string, bajo: number];

/* --------------------------------------------------------------- saludar */
/** El brazo que sube: a la derecha, a la izquierda o los dos. `altos` es la
 *  fila de la mano de cada brazo, que baja de ahí hasta el hombro. Saludando
 *  con los dos son tres tiempos: a media altura, arriba, y arriba alternando
 *  una mano y otra. */
const saludo = (b: string[], lado: Onda): Sprite => {
  const columnas = lado === "izq" ? [1] : lado === "dos" ? [1, 10] : [10];
  const dos = columnas.length > 1;
  const alturas = (una: number, otra: number): number[] => columnas.map((_, k) => (k === 0 ? una : otra));
  const brazo = (altos: number[], ch: string): string[] => {
    const f = b.slice(0, 12);
    altos.forEach((y, k) => {
      const x = columnas[k];
      for (let i = y; i <= 6; i++) f[i] = parche(f[i], x, i === y ? ch : "o");
    });
    return f;
  };
  const pose = (altos: number[], ch: string): string[] =>
    ensamblar(brazo(altos, ch), izq.apoyada, der.apoyada);
  return [
    pose(alturas(4, 4), "o"),
    pose(alturas(dos ? 2 : 1, 2), dos ? "e" : "o"),
    ...(dos ? [pose(alturas(1, 3), "e")] : []),
  ];
};

export type Onda = "der" | "izq" | "dos";

/* --------------------------------------------------------------- respirar */
/** El torso sube (k<0) o baja (k>0) un píxel dejando cinturón y pies donde
 *  están: lo único que se mueve de verdad es el pecho. Al subir se copia la
 *  cintura y no el cinturón, que es la línea que sostiene la silueta. */
const respirar = (b: string[], k: number): string[] => {
  if (!k) return b.slice();
  const out = b.slice();
  for (let y = 6; y <= 10; y++) out[y] = b[Math.min(y - k, 10)] ?? b[y];
  return out;
};

/** Los frames de respiración de un agente (0 quieto, -1 arriba, 1 abajo) y su
 *  adorno: el parpadeo de la antena, la gorguera o la luz del auricular van en
 *  el frame de arriba, que es donde se nota. */
const enRespiracion = (b: string[], e: Estilo): Sprite => {
  const pico = e.respira.indexOf(-1);
  const adorno = pico < 0 ? e.respira.length - 1 : pico;
  return e.respira.map((k, i) => {
    const cuerpo = respirar(b, k);
    return ensamblar(e.gesto && i === adorno ? e.gesto(cuerpo) : cuerpo, izq.apoyada, der.apoyada);
  });
};

/* ------------------------------------------------------------------ estilos */
type Estilo = {
  gait: Gait;
  lider: "izq" | "der";
  onda: Onda;
  carga: Carga;
  tecleo: Tecla[];
  /** los frames de la respiración: 0 quieto, -1 torso arriba, 1 abajo */
  respira: number[];
  /** lo que hace de su manera al respirar, en el frame de arriba */
  gesto?: (f: string[]) => string[];
  ritmo: number;
  nervios: boolean;
  rebote: number;
};

type Pose = keyof typeof izq;
type Gait = [Pose, Pose][];

/** Las tresformas de andar. */
const GAITS: Record<string, Gait> = {
  // zancada normal: contacto, paso, contacto al revés, paso
  camina: [["apoyada", "alzada"], ["paso", "paso"], ["alzada", "apoyada"], ["paso", "paso"]],
  // marcha: piernas juntas que se alternan levantando un pie
  marca: [["paso", "corta"], ["paso", "paso"], ["corta", "paso"], ["paso", "paso"]],
  // de puntillas: pasos cortos, un pie siempre en el aire
  puntillas: [["apoyada", "corta"], ["paso", "paso"], ["corta", "apoyada"], ["paso", "paso"]],
};

/** Cada agente con su manera de moverse. El `ritmo` divide al reloj: cuanto
 *  más alto, más rápido teclea (y también más rápido respira). `nervios` le
 *  hace temblar. */
export const ESTILO: Record<AgenteId, Estilo> = {
  // el que va deprisa y seguro
  wallet: {
    gait: GAITS.camina,
    lider: "izq",
    onda: "der",
    carga: "dos",
    tecleo: [
      [7, manos.medioI.izq, manos.medioD.der, 0],
      [8, manos.arriba.izq, manos.arriba.der, 1],
      [10, manos.abajo.izq, manos.abajo.der, 0],
      [8, manos.flashI.izq, manos.flashD.der, 1],
    ],
    respira: [0, -1, 0],
    ritmo: 1.15,
    nervios: false,
    rebote: 1,
  },
  // el que busca y pulsa, una mano cada vez
  transaction: {
    gait: GAITS.camina,
    lider: "der",
    onda: "izq",
    carga: "una",
    tecleo: [
      [8, manos.soloIzq.izq, manos.soloIzq.der, 0],
      [7, manos.soloDer.izq, manos.soloDer.der, 1],
      [6, manos.soloIzq.izq, manos.soloDer.der, 0],
      [8, manos.soloDer.izq, manos.soloIzq.der, 1],
    ],
    respira: [0, 1, 0],
    ritmo: 0.75,
    nervios: false,
    rebote: 1,
  },
  // el que va marcado, despacio y sin apartar las manos
  contract: {
    gait: GAITS.marca,
    lider: "izq",
    onda: "dos",
    carga: "hombro",
    tecleo: [
      [8, manos.arriba.izq, manos.arriba.der, 0],
      [8, manos.arriba.izq, manos.arriba.der, 0],
      [9, manos.cerrado.izq, manos.cerrado.der, 1],
      [7, manos.medioI.izq, manos.medioD.der, 0],
    ],
    respira: [0, -1],
    gesto: f => puntos(f, 3, [4, "o"], [7, "o"]),
    ritmo: 0.6,
    nervios: false,
    rebote: 2,
  },
  // el que no hace ruido: de puntillas y teclea reposado
  research: {
    gait: GAITS.puntillas,
    lider: "der",
    onda: "izq",
    carga: "dos",
    tecleo: [
      [7, manos.medioI.izq, manos.arriba.der, 0],
      [8, manos.arriba.izq, manos.arriba.der, 1],
      [6, manos.flashI.izq, manos.arriba.der, 0],
      [9, manos.medioD.izq, manos.arriba.der, 1],
    ],
    respira: [0, -1, 0],
    gesto: f => puntos(f, 0, [6, "o"]),
    ritmo: 0.85,
    nervios: false,
    rebote: 1,
  },
  // el centinela: Heavy y rapido, con hombreras que se ven al andar
  monitoring: {
    gait: GAITS.marca,
    lider: "der",
    onda: "der",
    carga: "una",
    tecleo: [
      [7, manos.flashI.izq, manos.flashD.der, 0],
      [7, manos.flashD.izq, manos.flashI.der, 0],
      [9, manos.cerrado.izq, manos.cerrado.der, 0],
      [7, manos.flashD.izq, manos.flashI.der, 1],
    ],
    respira: [0, -1, 0],
    gesto: f => puntos(f, 1, [10, "e"]),
    ritmo: 1.5,
    nervios: false,
    rebote: 2,
  },
  // el que va con el miedo en el cuerpo: le tiembla todo
  risk: {
    gait: GAITS.puntillas,
    lider: "izq",
    onda: "dos",
    carga: "una",
    tecleo: [
      [7, manos.flashI.izq, manos.flashD.der, 1],
      [8, manos.flashD.izq, manos.flashI.der, 0],
      [6, manos.flashI.izq, manos.flashI.der, 1],
      [9, manos.medioI.izq, manos.medioD.der, 0],
    ],
    respira: [0, 1, 0],
    gesto: f => puntos(f, 6, [4, "o"], [7, "o"]),
    ritmo: 1.7,
    nervios: true,
    rebote: 1,
  },
  // el que redacta sin prisa, con las manos bajas
  explanation: {
    gait: GAITS.camina,
    lider: "izq",
    onda: "izq",
    carga: "hombro",
    tecleo: [
      [9, manos.abajo.izq, manos.abajo.der, 0],
      [8, manos.medioI.izq, manos.abajo.der, 0],
      [10, manos.abajo.izq, manos.abajo.der, 1],
      [7, manos.medioD.izq, manos.medioI.der, 0],
    ],
    respira: [0, -1, 0],
    gesto: f => puntos(f, 0, [5, "o"]),
    ritmo: 0.7,
    nervios: false,
    rebote: 1,
  },
};

/* ------------------------------------------------------------------ alarma */
/** Enciende el visor: entre el borde oscuro y el contorno queda una franja de
 *  acento. Ese acento es justo lo que la paleta pone blanco cuando al agente le
 *  salta la alarma, así que el mismo dibujo sirve de luz y de aviso. */
const visorCaliente = (b: string[]): string[] => {
  const fila = b[3];
  const ini = fila.indexOf("o");
  const fin = fila.lastIndexOf("o");
  if (ini < 0 || fin - ini < 4) return b.slice();
  let out = "";
  for (let x = 0; x < ANCHO; x++) out += x > ini + 1 && x < fin - 1 ? "e" : fila[x];
  return con(b, 3, out);
};

/** El pecho se enciende a la vez que el visor: la banda clara pasa a acento. */
const pechoCaliente = (b: string[]): string[] => con(b, 9, b[9].replace(/w/g, "e"));

export type Alerta = {
  /** por frame: la fila donde caen las manos y si el cuerpo se hunde */
  manos: Tecla[];
  piernas: Gait;
  /** píxeles que sube el torso en cada frame */
  alza: number[];
  /** en qué frame hace su gesto propio (por defecto, el del medio) */
  marco?: number;
  gesto?: (f: string[]) => string[];
};

/** La alarma: el visor encendido para todos, el cuerpo de cada uno. */
const ALERTAS: Record<AgenteId, Alerta> = {
  // se planta con las manos en las caderas y luego las sube al pecho
  wallet: {
    manos: [
      [10, manos.abajo.izq, manos.abajo.der, 0],
      [10, manos.medioI.izq, manos.medioD.der, 1],
      [8, manos.medioI.izq, manos.medioD.der, 0],
    ],
    piernas: [["apoyada", "apoyada"], ["apoyada", "alzada"], ["paso", "paso"]],
    alza: [0, 0, -1],
  },
  // señala con un dedo y guarda la otra mano en la cadera
  transaction: {
    manos: [
      [8, manos.abajo.izq, manos.flashD.der, 0],
      [7, manos.medioI.izq, manos.flashD.der, 1],
      [6, manos.medioD.izq, manos.flashD.der, 0],
    ],
    piernas: [["paso", "paso"], ["apoyada", "paso"], ["paso", "paso"]],
    alza: [0, 0, -1],
  },
  // se lleva las dos manos a la cara y se yergue: esto no puede ser
  contract: {
    manos: [
      [5, manos.abajo.izq, manos.abajo.der, 0],
      [4, manos.medioI.izq, manos.medioD.der, 1],
      [5, manos.abajo.izq, manos.abajo.der, 0],
    ],
    piernas: [["apoyada", "apoyada"], ["paso", "paso"], ["apoyada", "apoyada"]],
    alza: [0, -1, 0],
    marco: 2,
    gesto: f => puntos(f, 3, [3, "o"], [8, "o"]),
  },
  // se tapa la cara y retrocede, sin soltar el susto
  research: {
    manos: [
      [5, manos.rostro.izq, manos.rostro.der, 0],
      [5, manos.rostro.izq, manos.rostro.der, 1],
      [6, manos.rostro.izq, manos.medioD.der, 0],
    ],
    piernas: [["paso", "paso"], ["paso", "corta"], ["corta", "paso"]],
    alza: [0, 0, 0],
    marco: 2,
    gesto: f => puntos(f, 0, [6, "o"]),
  },
  // el centinela se yergue y levanta los brazos a los lados
  monitoring: {
    manos: [
      [10, manos.abajo.izq, manos.abajo.der, 0],
      [10, manos.abajo.izq, manos.abajo.der, 1],
      [7, manos.cuello.izq, manos.cuello.der, 0],
    ],
    piernas: [["apoyada", "apoyada"], ["apoyada", "apoyada"], ["paso", "paso"]],
    alza: [0, -1, -1],
  },
  // retrocede con los brazos cruzados y el cuello de pinchos erizado
  risk: {
    manos: [
      [8, manos.cerrado.izq, manos.cerrado.der, 0],
      [8, manos.cerrado.izq, manos.cerrado.der, 1],
      [7, manos.cerrado.izq, manos.cerrado.der, 0],
    ],
    piernas: [["apoyada", "atras"], ["atras", "corta"], ["corta", "apoyada"]],
    alza: [0, 0, 0],
    marco: 2,
    gesto: f => puntos(f, 6, [4, "o"], [7, "o"]),
  },
  // levanta una mano explicando y la otra acabando la frase
  explanation: {
    manos: [
      [8, manos.abajo.izq, manos.flashD.der, 0],
      [7, manos.medioI.izq, manos.flashD.der, 1],
      [6, manos.medioD.izq, manos.arriba.der, 0],
    ],
    piernas: [["apoyada", "apoyada"], ["paso", "paso"], ["apoyada", "apoyada"]],
    alza: [0, -1, 0],
    marco: 2,
    gesto: f => puntos(f, 0, [6, "o"]),
  },
};

/* ------------------------------------------------------------------- ciclos */
const gaitDe = (g: Gait, lider: "izq" | "der"): [string[], string[]][] => {
  const par = g.map(([a, b]) => (lider === "izq" ? [izq[a], der[b]] : [der[b], izq[a]]));
  return par as [string[], string[]][];
};

const ciclo = (b: string[], g: Gait, lider: "izq" | "der", carga: Carga | null): Sprite => {
  const frames = gaitDe(g, lider);
  return frames.map(([pi, pd], i) => {
    const torso = carga
      ? torsoCarga(b, carga)
      : i === 0 || i === 2
        ? lider === "izq"
          ? brazoAtrasDer(b)
          : brazoAtrasIzq(b)
        : b.slice(0, 12);
    return ensamblar(torso, pi, pd);
  });
};

const enAlarma = (b: string[], a: Alerta, lider: "izq" | "der"): Sprite => {
  const caliente = pechoCaliente(visorCaliente(b));
  const piernas = gaitDe(a.piernas, lider);
  return a.manos.map(([fila, i, d, bajo], k) => {
    let torso = respirar(caliente, a.alza[k] ?? 0);
    if (a.gesto && k === (a.marco ?? 1)) torso = a.gesto(torso);
    return ensamblar(tecleo(torso, fila, i, d, bajo), piernas[k][0], piernas[k][1]);
  });
};

export const SPRITES: Record<AgenteId, Record<Postura, Sprite>> = Object.fromEntries(
  (Object.keys(ESTILO) as AgenteId[]).map(id => {
    const e = ESTILO[id];
    const b = cuerpoDe(id);
    return [
      id,
      {
        idle: enRespiracion(b, e),
        walk: ciclo(b, e.gait, e.lider, null),
        type: e.tecleo.map(([fila, a, c, bajo]) => tecleo(b, fila, a, c, bajo)),
        wave: saludo(b, e.onda),
        carry: ciclo(b, e.gait, e.lider, e.carga),
        alert: enAlarma(b, ALERTAS[id], e.lider),
      },
    ];
  }),
) as Record<AgenteId, Record<Postura, Sprite>>;

/** Revisa todos los sprites ya ensamblados: lo usa el verificador. */
export function validarSprites(): string[] {
  const errores: string[] = [];
  (Object.keys(SPRITES) as AgenteId[]).forEach(id => {
    const estados = SPRITES[id];
    (Object.keys(estados) as Postura[]).forEach(estado => {
      estados[estado].forEach((f, i) => {
        if (f.length !== ALTO) errores.push(`${id}:${estado}[${i}] ${f.length} filas`);
        f.forEach((fila, y) => {
          if (fila.length !== ANCHO)
            errores.push(`${id}:${estado}[${i}] fila ${y}: ${fila.length} cols "${fila}"`);
        });
      });
    });
  });
  return errores;
}
