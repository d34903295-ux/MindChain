"""Comprueba el ciclo de los robots de la sala.

La sala se dibuja con un solo reloj (useFrame) y el recorrido de cada agente
sale de `frontend/components/movimiento.ts`. Este script compila ese módulo con
el TypeScript que ya tiene el proyecto y ejecuta las comprobaciones, para que
el movimiento no dependa de abrir el navegador a ojo.

Además del ciclo, mira el otro lado de la costura: `modoEnCiclo` dice en qué
postura está cada agente, y si esa postura no existe en `SPRITES` el componente
se queda con `?? idle` y nadie se entera de que un estado nuevo se quedó sin
animación. Se comprueba con los frames ya ensamblados de los siete agentes.

Uso: python scripts/verificar_movimiento.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FUENTE = RAIZ / "frontend" / "components" / "movimiento.ts"
SPRITES = RAIZ / "frontend" / "components" / "sprites.ts"

PRUEBAS = r"""
import { faseEnCiclo, modoEnCiclo, posicionEnCiclo, duracionCiclo } from "./movimiento.js";

type Punto = [number, number];
type Ruta = [Punto, Punto, Punto];

declare const console: { log(x: string): void };

const ruta: Ruta = [[0, 0], [40, 30], [70, 52]];
const fallos: string[] = [];
const cuenta = { total: 0 };
const ok = (cond: boolean, msg: string) => {
  cuenta.total += 1;
  if (!cond) fallos.push(msg);
};

ok(Math.abs(posicionEnCiclo(0, ruta).x) < 1e-9, "en c=0 el agente esta en su puesto");
ok(posicionEnCiclo(0, ruta).andando === false, "en c=0 el agente esta quieto");

ok(posicionEnCiclo(0.4, ruta).andando === true, "en c=0.4 el agente va hacia la mesa");
ok(posicionEnCiclo(0.4, ruta).x > 0, "en c=0.4 el agente avanza en x");
ok(posicionEnCiclo(0.4, ruta).x < 70, "en c=0.4 el agente aun no llega a la mesa");

const mesa = posicionEnCiclo(0.58, ruta);
ok(mesa.x === 40 && mesa.y === 30, "en c=0.58 el agente esta en la mesa");
ok(mesa.andando === false, "en c=0.58 el agente esta quieto en la mesa");

ok(posicionEnCiclo(0.75, ruta).andando === true, "en c=0.75 el agente vuelve");
const vueltaMedia = posicionEnCiclo(0.75, ruta);
ok(vueltaMedia.x > 40 && vueltaMedia.x < 70, "en c=0.75 el agente va del punto medio a la mesa");
ok(posicionEnCiclo(0.95, ruta).andando === false, "en c=0.95 el agente esta quieto");

const vuelta = posicionEnCiclo(1, ruta);
ok(vuelta.x === 0 && vuelta.y === 0, "en c=1 el agente vuelve al puesto");

const fases = [0, 0.137, 0.274, 0.411, 0.548, 0.685, 0.822].map(f =>
  faseEnCiclo(0, 260, f),
);
ok(new Set(fases.map(v => v.toFixed(3))).size === 7, "los siete agentes van desfasados");
ok(fases.every(v => v >= 0 && v < 1), "las fases quedan en el intervalo del ciclo");

ok(faseEnCiclo(0, 260, 0.3) !== faseEnCiclo(150, 260, 0.3), "el ciclo avanza con el reloj");

const ciclo = duracionCiclo(260);
ok(ciclo === 572, "el ciclo dura 2.2 veces el periodo");
ok(ciclo / 60 > 9 && ciclo / 60 < 10, "el ciclo dura entre 9 y 10 segundos a 60fps");

const fuera = faseEnCiclo(999999, 260, 0.42);
ok(fuera >= 0 && fuera < 1, "el ciclo no se sale con relojes muy altos");

ok(modoEnCiclo(0.1) === "type", "al principio teclea en su puesto");
ok(modoEnCiclo(0.4) === "walk", "de camino a la mesa va andando");
ok(modoEnCiclo(0.58) === "wave", "al llegar a la mesa saluda");
ok(modoEnCiclo(0.75) === "carry", "de vuelta carga el paquete");
ok(modoEnCiclo(0.95) === "type", "al final vuelve a teclear");

/* Y la vuelta entera, no solo cinco puntos: ningun tramo se queda sin cubrir y
   ningun tramo devuelve una postura que no exista. */
const POSTURAS = ["type", "walk", "wave", "carry"];
const vistos = new Set<string>();
for (let i = 0; i <= 1000; i++) {
  const c = i / 1000;
  vistos.add(modoEnCiclo(c));
  ok(posicionEnCiclo(c, ruta).andando === ((c >= 0.28 && c < 0.55) || (c >= 0.62 && c < 0.89)),
    `en c=${c.toFixed(3)} el agente se mueve justo en los tramos de camino`);
}
POSTURAS.forEach(p => ok(vistos.has(p), `el ciclo nunca devuelve la postura "${p}"`));
[...vistos].forEach(p => ok(POSTURAS.includes(p), `el ciclo devuelve la postura "${p}", que no existe`));
ok(vistos.size === POSTURAS.length, `el ciclo recorre ${vistos.size} posturas de ${POSTURAS.length}`);

if (fallos.length) {
  throw new Error(fallos.join(" | "));
}
console.log(`ciclo de los robots correcto: ${cuenta.total} comprobaciones, ${(ciclo / 60).toFixed(2)}s por vuelta`);
"""

# El otro lado de la costura: lo que el ciclo pide, el sprite lo tiene que dar.
ESTADOS = r"""
import { modoEnCiclo } from "./movimiento.js";
import { SPRITES } from "./sprites.js";

declare const console: { log(x: string): void };

const fallos: string[] = [];
const estadosDe = (id: string): Record<string, string[][]> =>
  SPRITES[id as keyof typeof SPRITES] as unknown as Record<string, string[][]>;

const modos = [...new Set(Array.from({ length: 1001 }, (_, i) => modoEnCiclo(i / 1000)))];
const ids = Object.keys(SPRITES);

for (const modo of modos) {
  const sinEstado = ids.filter(id => estadosDe(id)[modo] === undefined);
  if (sinEstado.length) {
    fallos.push(
      `el ciclo pone "${modo}" y ${sinEstado.join(", ")} no tienen ese estado: se dibujarian en idle sin avisar`,
    );
  }
  const vacios = ids.filter(id => (estadosDe(id)[modo] ?? []).length === 0);
  if (vacios.length) {
    fallos.push(`el ciclo pone "${modo}" y ${vacios.join(", ")} lo tienen sin frames`);
  }
}

/* Y al reves: los siete agentes tienen que traer los mismos estados. Si uno se
   queda atras, ese estado se le cae al idle sin que nada lo diga. */
const referencia = ids.length ? Object.keys(estadosDe(ids[0])).sort() : [];
ids.forEach(id => {
  const suyos = Object.keys(estadosDe(id)).sort();
  if (suyos.join(",") !== referencia.join(",")) {
    fallos.push(`${id}: tiene [${suyos.join(", ")}] y ${ids[0]} tiene [${referencia.join(", ")}]`);
  }
});

if (fallos.length) {
  fallos.forEach(f => console.log("  MAL " + f));
  throw new Error(`${fallos.length} costuras rotas entre el ciclo y los sprites`);
}
console.log(`costura del ciclo correcta: sus ${modos.length} modos existen en los ${ids.length} agentes`);
"""


def compila(destino: Path, fuentes: list[Path], extra: list[str]) -> tuple[int, str]:
    tsc = RAIZ / "frontend" / "node_modules" / ".bin" / ("tsc.cmd" if sys.platform == "win32" else "tsc")
    if not tsc.exists():
        return 1, "falta typescript en frontend/node_modules"
    hecho = subprocess.run(
        [str(tsc), "--target", "ES2020", "--module", "ES2020", "--moduleResolution", "bundler",
         *extra, "--outDir", str(destino / "js"), *[str(f) for f in fuentes]],
        capture_output=True,
        text=True,
    )
    return hecho.returncode, hecho.stdout or hecho.stderr


def main() -> int:
    for fuente in (FUENTE, SPRITES):
        if not fuente.exists():
            print(f"no existe {fuente}")
            return 1

    with tempfile.TemporaryDirectory() as tmp:
        destino = Path(tmp)
        (destino / "movimiento.ts").write_text(FUENTE.read_text(encoding="utf-8"), encoding="utf-8")
        (destino / "sprites.ts").write_text(SPRITES.read_text(encoding="utf-8"), encoding="utf-8")
        (destino / "prueba.ts").write_text(PRUEBAS, encoding="utf-8")
        (destino / "estados.ts").write_text(ESTADOS, encoding="utf-8")

        # el ciclo, con los tipos puestos
        code, salida = compila(destino, [destino / "movimiento.ts", destino / "prueba.ts"], ["--strict"])
        if code != 0:
            print("el modulo no compila:")
            print(salida)
            return 1
        correr = subprocess.run(
            ["node", str(destino / "js" / "prueba.js")],
            capture_output=True,
            text=True,
        )
        if correr.returncode != 0:
            print("fallos en el ciclo de los robots:")
            print(correr.stdout or correr.stderr)
            return 1

        # el ciclo contra los sprites ya ensamblados (sprites.ts necesita sus
        # vecinos, que aqui no están: por eso esto va sin --strict)
        code, salida = compila(
            destino, [destino / "movimiento.ts", destino / "sprites.ts", destino / "estados.ts"], ["--noCheck"]
        )
        if code != 0:
            print("los estados no compilan:")
            print(salida)
            return 1
        estados = subprocess.run(
            ["node", str(destino / "js" / "estados.js")],
            capture_output=True,
            text=True,
        )
        if estados.returncode != 0:
            print("el ciclo y los sprites no encajan:")
            print(estados.stdout or estados.stderr)
            return 1
        print(estados.stdout.strip())

        print(correr.stdout.strip())
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

