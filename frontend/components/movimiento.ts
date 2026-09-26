export type Punto = [number, number];
export type Ruta = [Punto, Punto, Punto];

export type Pose = {
  x: number;
  y: number;
  dx: number;
  andando: boolean;
};

const QUIETO = (c: number): Pose => ({ x: 0, y: 0, dx: 0, andando: false });

const DE_0_A_1 = 0.28;
const VA_A_1 = 0.55;
const EN_MESA_HASTA = 0.62;
const VUELVE_HASTA = 0.89;

export function posicionEnCiclo(c: number, ruta: Ruta): Pose {
  if (c >= DE_0_A_1 && c < VA_A_1) {
    const f = (c - DE_0_A_1) / (VA_A_1 - DE_0_A_1);
    return {
      x: ruta[0][0] + (ruta[1][0] - ruta[0][0]) * f,
      y: ruta[0][1] + (ruta[1][1] - ruta[0][1]) * f,
      dx: ruta[1][0] - ruta[0][0],
      andando: true,
    };
  }
  if (c >= VA_A_1 && c < EN_MESA_HASTA) {
    return { x: ruta[1][0], y: ruta[1][1], dx: ruta[2][0] - ruta[1][0], andando: false };
  }
  if (c >= EN_MESA_HASTA && c < VUELVE_HASTA) {
    const f = (c - EN_MESA_HASTA) / (VUELVE_HASTA - EN_MESA_HASTA);
    return {
      x: ruta[1][0] + (ruta[2][0] - ruta[1][0]) * f,
      y: ruta[1][1] + (ruta[2][1] - ruta[1][1]) * f,
      dx: ruta[2][0] - ruta[1][0],
      andando: true,
    };
  }
  return QUIETO(c);
}

export function faseEnCiclo(t: number, dur: number, fase: number): number {
  const vuelta = t / (dur * 2.2) + fase;
  return vuelta - Math.floor(vuelta);
}

export function duracionCiclo(dur: number): number {
  return dur * 2.2;
}

export type ModoAgente = "type" | "walk" | "wave" | "carry";

export function modoEnCiclo(c: number): ModoAgente {
  if (c >= DE_0_A_1 && c < VA_A_1) return "walk";
  if (c >= VA_A_1 && c < EN_MESA_HASTA) return "wave";
  if (c >= EN_MESA_HASTA && c < VUELVE_HASTA) return "carry";
  return "type";
}
