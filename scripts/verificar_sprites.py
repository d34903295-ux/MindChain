"""Comprueba los sprites de los agentes antes de que lleguen a la pantalla.

Los sprites están escritos a mano como rejillas de caracteres. Un carácter
de más o de menos no rompe la página: rompe el dibujo en silencio, y eso es
peor. Este script lo delata por capas:

1. Las filas escritas a mano. Cada una mide 12 columnas (cuerpo entero) o 6
   (media fila de pierna o de mano), y solo usa letras de la paleta que
   declara AgentePixel.tsx. Ojo con cómo se localizan: por FORMA (4+ letras
   con al menos un punto y sin barra), nunca por la lista de letras. Filtrar
   por lista era justo el agujero: las filas nuevas llevan `l` (luz) y `s`
   (sombra) y se escapaban de la medida sin avisar.
2. Los píxeles que se pintan uno a uno: `parche`, `puntos` y `con`. La
   expresión regular de antes no veía la llamada de fuera de un `parche`
   anidado (`parche(parche(f[8], 10, "o"), 9, "e")`), así que ahora las llamadas
   se recorren contando paréntesis. También la fila del torso donde caen las
   manos, que antes no se miraba en ninguna parte.
3. Los frames ya ensamblados: compila `sprites.ts` con el TypeScript del
   proyecto y ejecuta `validarSprites()` más las reglas de sala — los mismos
   estados para todos los agentes, los mismos frames en cada estado, ninguna
   animación repetida y ni un píxel fuera de la paleta.

    python scripts/verificar_sprites.py [ruta/sprites.ts] [ruta/AgentePixel.tsx]

Sale con 0 si todo cuadra y con 1 en cuanto algo no lo hace.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import tempfile

CUERPO = 12
MEDIA = 6
ALTO = 16

RAIZ = pathlib.Path(__file__).resolve().parent.parent
RUTA = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "frontend" / "components" / "sprites.ts"
RUTA_PALETA = (
    pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else RAIZ / "frontend" / "components" / "AgentePixel.tsx"
)


def linea_de(pos: int, texto: str) -> int:
    return texto[:pos].count("\n") + 1


def donde_de(pos: int, texto: str) -> str:
    """`ACCESORIO.monitoring`, `base`, `manos.arriba`... para que el error diga
    en qué bloque está la fila y no solo en qué línea."""
    seccion = clave = ""
    for linea in reversed(texto[:pos].split("\n")):
        if not seccion:
            m = re.match(r"^(?:export )?const (\w+)", linea)
            if m:
                seccion = m.group(1)
        if not clave:
            m = re.match(r"^ {2}(\w+)\s*:", linea)
            if m:
                clave = m.group(1)
        if seccion and clave:
            break
    return f"{seccion}.{clave}" if clave else (seccion or "?")


def claves_de_paleta(texto: str) -> set[str]:
    """Las claves de la paleta de AgentePixel.tsx: la base `P` y la que cada
    agente monta encima con su color (c = color, e = acento, s y l = sombra y
    luz de ese color). El punto se suma aparte porque en pixel.tsx es el
    píxel transparente, no una clave de color."""
    claves = {"."}
    for bloque in re.finditer(r"Paleta\s*=\s*\{(.*?)\}", texto, re.S):
        for m in re.finditer(r"([A-Za-z])\s*:", bloque.group(1)):
            claves.add(m.group(1))
    return claves


def literal(texto: str) -> str | None:
    """El contenido si `texto` es una cadena literal; None si es una variable."""
    m = re.fullmatch(r"\"([^\"]*)\"|'([^']*)'", texto.strip())
    if not m:
        return None
    return m.group(1) if m.group(1) is not None else m.group(2)


def llamadas(texto: str, nombre: str):
    """Cada `nombre(...)` del archivo con sus argumentos de primer nivel. Los
    paréntesis anidados cuentan como un argumento entero, que es lo que no
    veía la expresión regular anterior: media parte de los `parche` de
    sprites.ts son `parche(parche(f[8], 10, "o"), 9, "e")`."""
    for m in re.finditer(r"(?<![\w.$])" + re.escape(nombre) + r"\s*\(", texto):
        nivel, comilla, cortes, i = 1, "", [], m.end()
        while i < len(texto) and nivel > 0:
            ch = texto[i]
            if comilla:
                if ch == "\\":
                    i += 2
                    continue
                if ch == comilla:
                    comilla = ""
            elif ch in "\"'`":
                comilla = ch
            elif ch in "([{":
                nivel += 1
            elif ch in ")]}":
                nivel -= 1
                if nivel == 0:
                    break
            elif ch == "," and nivel == 1:
                cortes.append(i - m.end())
            i += 1
        cuerpo = texto[m.end() : i]
        args, prev = [], 0
        for corte in cortes:
            args.append(cuerpo[prev:corte].strip())
            prev = corte + 1
        args.append(cuerpo[prev:].strip())
        yield m.start(), args


def ancho_esperado(ancho: int) -> int:
    """A 6 o a 12. La fila se cuenta como cuerpo si pasa de la mitad de sus
    columnas, y como media fila si no: es la mejor guess cuando la fila ya
    viene descuadrada, y con la longitud a la vista el error dice siempre cuál
    de las dos se esperaba."""
    return CUERPO if ancho * 2 > CUERPO + MEDIA else MEDIA


def revisa_filas(texto: str, paleta: set[str]) -> tuple[list, list, list[str]]:
    """Las filas escritas a mano: dónde están, cuántas son de cada clase y qué
    está mal. Se buscan por forma y no por letra a propósito: una `s` o una `l`
    de más no puede esconder una fila, y un carácter que no está en la paleta
    tampoco, porque se reporta como lo que es."""
    cuerpo, medias, malos = [], [], []
    for m in re.finditer(r'"([^"\n]{4,})"', texto):
        fila = m.group(1)
        if "." not in fila or "/" in fila:
            # los píxeles sueltos van en argumentos de un carácter ("o"), las
            # rodillas y los nombres de enum van sin puntos, y las rutas de
            # import llevan barra.
            continue
        donde = f"{RUTA.name} linea {linea_de(m.start(), texto)} ({donde_de(m.start(), texto)})"
        esperado = ancho_esperado(len(fila))
        (cuerpo if esperado == CUERPO else medias).append(fila)

        fuera = sorted({c for c in fila if c not in paleta})
        if fuera:
            malos.append(
                f"{donde}: la fila usa {' '.join(repr(c) for c in fuera)}, que no esta en la paleta de "
                f"{RUTA_PALETA.name} ({' '.join(sorted(paleta))}); ese pixel se dibujaria como nada"
            )
        if len(fila) != esperado:
            malos.append(
                f"{donde}: la fila mide {len(fila)} columnas y se esperaban {esperado} "
                f"({'cuerpo entero' if esperado == CUERPO else 'media fila'}): {fila!r}"
            )
    return cuerpo, medias, malos


def revisa_pixel(texto: str, paleta: set[str]) -> list[str]:
    """Los píxeles sueltos: dónde caen y de qué color son. Todos tienen que
    estar dentro de la rejilla y usar un carácter de la paleta."""
    malos = []

    def donde(pos: int) -> str:
        return f"{RUTA.name} linea {linea_de(pos, texto)} ({donde_de(pos, texto)})"

    def fuera_de_paleta(ch: str, pos: int, que: str) -> None:
        malos.append(
            f"{donde(pos)}: {que} con el caracter {ch!r}, que no esta en la paleta de "
            f"{RUTA_PALETA.name}; se dibujaria como nada"
        )

    for pos, args in llamadas(texto, "parche"):
        if len(args) != 3 or not re.fullmatch(r"\d+", args[1]):
            continue
        x = int(args[1])
        if not 0 <= x < CUERPO:
            malos.append(f"{donde(pos)}: parche en la columna {x}; el cuerpo va de 0 a {CUERPO - 1}")
        fila = literal(args[0])
        if fila is not None and len(fila) != CUERPO:
            malos.append(f"{donde(pos)}: parche sobre una fila de {len(fila)} columnas, y se parchean {CUERPO}")
        ch = literal(args[2])
        if ch is None:
            continue
        if len(ch) != 1:
            malos.append(f"{donde(pos)}: parche con {len(ch)} caracteres, y cada parche es un solo pixel: {ch!r}")
        elif ch not in paleta:
            fuera_de_paleta(ch, pos, "parche")

    for pos, args in llamadas(texto, "puntos"):
        if len(args) < 3 or not re.fullmatch(r"\d+", args[1]):
            continue
        y = int(args[1])
        if not 0 <= y < ALTO:
            malos.append(f"{donde(pos)}: puntos en la fila {y}; el sprite va de 0 a {ALTO - 1}")
        for par in args[2:]:
            m = re.fullmatch(r"\[\s*(\d+)\s*,\s*\"([^\"]*)\"\s*\]", par)
            if not m:
                continue
            x, ch = int(m.group(1)), m.group(2)
            if not 0 <= x < CUERPO:
                malos.append(f"{donde(pos)}: puntos en la columna {x}; el cuerpo va de 0 a {CUERPO - 1}")
            if len(ch) != 1:
                malos.append(f"{donde(pos)}: puntos con {len(ch)} caracteres, y cada punto es un pixel: {ch!r}")
            elif ch not in paleta:
                fuera_de_paleta(ch, pos, "puntos")

    for pos, args in llamadas(texto, "con"):
        if len(args) != 3 or not re.fullmatch(r"\d+", args[1]):
            continue
        y = int(args[1])
        if not 0 <= y < ALTO:
            malos.append(f"{donde(pos)}: con en la fila {y}; el sprite va de 0 a {ALTO - 1} (y con -1 no pinta nada)")
        fila = literal(args[2])
        if fila is not None and len(fila) != CUERPO:
            malos.append(f"{donde(pos)}: con sobre una fila de {len(fila)} columnas, y se pintan {CUERPO}")

    return malos


def revisa_manos(texto: str) -> list[str]:
    """`[fila, izq, der, bajo]`, que es donde caen las manos: tiene que caber en
    el sprite contando el hundimiento del cuerpo. La comprobación anterior
    buscaba `tecleo(<numero>,` y no aparecía nunca: los números de fila viven en
    las tuplas de ESTILO y de ALERTAS, no en las llamadas."""
    malos = []

    def donde_de_manos(pos: int) -> str:
        return f"{RUTA.name} linea {linea_de(pos, texto)} ({donde_de(pos, texto)})"

    def chequea(fila: int, bajo: int, donde: str) -> None:
        if bajo not in (0, 1):
            malos.append(f"{donde}: hundimiento de {bajo}; el cuerpo solo baja un pixel (0 o 1)")
        elif fila - bajo < 0:
            malos.append(f"{donde}: las manos caen en la fila {fila - bajo} con hundimiento {bajo}, fuera del sprite")
        elif fila > ALTO - 1:
            malos.append(f"{donde}: las manos caen en la fila {fila} de un sprite de {ALTO} filas (0 a {ALTO - 1})")

    for m in re.finditer(r"\[\s*(\d+)\s*,\s*manos\.\w+\.\w+\s*,\s*manos\.\w+\.\w+\s*,\s*(\d+)\s*\]", texto):
        chequea(int(m.group(1)), int(m.group(2)), donde_de_manos(m.start()))

    # tecleo(filas, fila, izq, der, bajo = 0), por si alguien lo llama con la fila puesta
    for pos, args in llamadas(texto, "tecleo"):
        if len(args) < 3 or not re.fullmatch(r"\d+", args[1]):
            continue
        bajo = int(args[4]) if len(args) > 4 and re.fullmatch(r"\d+", args[4]) else 0
        chequea(int(args[1]), bajo, donde_de_manos(pos))
    return malos


PRUEBA = """
import { SPRITES, ESTILO, validarSprites } from "./sprites.js";

declare const console: { log(x: string): void };

/* La paleta la lee este script de AgentePixel.tsx y la pasa aqui inyectada: si
   se anade o se quita una clave, esta comprobacion lo sigue sin tocarla. */
const PALETA = new Set(__PALETA__);
/* Los estados que la sala necesita de cada agente. `alert` entra aqui para que
   nadie se quede sin alarma sin enterarse. */
const OBLIGATORIOS = ["idle", "walk", "type", "wave", "carry", "alert"];

const fallos: string[] = [];
const ok = (cond: boolean, msg: string) => {
  if (!cond) fallos.push(msg);
};
const estadosDe = (id: string): Record<string, string[][]> =>
  SPRITES[id as keyof typeof SPRITES] as unknown as Record<string, string[][]>;

const ids = Object.keys(SPRITES);
ok(ids.length > 0, "SPRITES no tiene ningun agente");

/* 1. lo que el propio modulo ya se revisa: 12 columnas y 16 filas por frame */
validarSprites().forEach(e => fallos.push("frame descuadrado -> " + e));

/* 2. los mismos estados para todos, y ningun estado sin frames: una animacion
      vacia deja al robot sin pintar y una postura que falta cae al idle */
const estados = ids.length ? Object.keys(estadosDe(ids[0])).sort() : [];
ids.forEach(id => {
  const suyos = Object.keys(estadosDe(id)).sort();
  OBLIGATORIOS.forEach(e => ok(suyos.includes(e), `${id}: le falta el estado "${e}"`));
  ok(
    suyos.join(",") === estados.join(","),
    `${id}: tiene [${suyos.join(", ")}] y ${ids[0]} tiene [${estados.join(", ")}]`,
  );
  suyos.forEach(e => {
    const n = (estadosDe(id)[e] ?? []).length;
    ok(n > 0, `${id}:${e} no tiene ningun frame: al pintarlo sale un robot vacio`);
  });
});

/* 3. los mismos frames en todos. idle y wave son las dos que el modulo declara
      desiguales (respirar son 2 o 3, y saludar con los dos brazos son tres
      tiempos); el resto tienen que coincidir o el ciclo se descuadra. */
const RANGO: Record<string, number[]> = { idle: [2, 3], wave: [2, 3] };
estados.forEach(e => {
  const rango = RANGO[e];
  const cuenta = new Map<number, string[]>();
  ids.forEach(id => {
    const n = (estadosDe(id)[e] ?? []).length;
    if (rango) {
      ok(
        n >= rango[0] && n <= rango[1],
        `${id}:${e} tiene ${n} frames y ${e} documenta ${rango[0]} o ${rango[1]}`,
      );
    }
    cuenta.set(n, [...(cuenta.get(n) ?? []), id]);
  });
  if (!rango && cuenta.size > 1) {
    const donde = [...cuenta.entries()].map(([n, g]) => `${n} frames -> ${g.join(", ")}`).join(" | ");
    fallos.push(`${e}: los agentes no tienen los mismos frames -> ${donde}`);
  }
});
/* y el porque de esas dos excepciones, para que no se ensanchen solas */
ids.forEach(id => {
  const e = ESTILO[id as keyof typeof ESTILO];
  const s = estadosDe(id);
  const saludo = e.onda === "dos" ? 3 : 2;
  ok(
    (s.wave ?? []).length === saludo,
    `${id}:wave tiene ${(s.wave ?? []).length} frames y saludar con "${e.onda}" son ${saludo}`,
  );
  ok(
    (s.idle ?? []).length === e.respira.length,
    `${id}:idle tiene ${(s.idle ?? []).length} frames y respira define ${e.respira.length}`,
  );
  ok(
    e.respira.every(k => k === -1 || k === 0 || k === 1),
    `${id}: respira solo admite -1, 0 o 1 (arriba, quieto, abajo)`,
  );
});

/* 4. ni un pixel fuera de la paleta: un caracter que no existe se dibuja como
      nada, asi que el sprite sale con un agujero y nadie se entera */
ids.forEach(id => {
  const s = estadosDe(id);
  Object.keys(s).forEach(e => {
    s[e].forEach((frame, i) => {
      frame.forEach((fila, y) => {
        for (let x = 0; x < fila.length; x++) {
          const ch = fila[x];
          ok(
            PALETA.has(ch),
            `${id}:${e}[${i}] fila ${y} col ${x}: "${ch}" no esta en la paleta de AgentePixel.tsx, se dibujaria como nada`,
          );
        }
      });
    });
  });
});

/* 5. cada agente se mueve a su manera, en TODOS los estados: si dos comparten
      animacion se pierde la gracia, y es justo lo que costaria mas notar */
estados.forEach(e => {
  const firmas = new Map<string, string[]>();
  ids.forEach(id => {
    const firma = JSON.stringify(estadosDe(id)[e] ?? []);
    firmas.set(firma, [...(firmas.get(firma) ?? []), id]);
  });
  firmas.forEach(grupo => {
    ok(grupo.length < 2, `${e}: ${grupo.join(" = ")} comparten la misma animacion`);
  });
});

/* Y ademas: ni el tempo ni los nervios pueden ser los mismos para todos. */
const ritmos = new Set(Object.values(ESTILO).map(e => e.ritmo));
if (ritmos.size < 5) {
  fallos.push("los ritmos son demasiado parecidos: " + [...ritmos].join(", "));
}
const nerviosos = Object.values(ESTILO).filter(e => e.nervios).length;
if (nerviosos < 1) {
  fallos.push("nadie tiembla: el estilo se queda sin chispa");
}
const gaits = new Set(Object.values(ESTILO).map(e => JSON.stringify(e.gait)));
if (gaits.size < 3) {
  fallos.push("faltan formas de andar: " + gaits.size);
}

let frames = 0;
estados.forEach(e => ids.forEach(id => {
  frames += (estadosDe(id)[e] ?? []).length;
}));

if (fallos.length) {
  fallos.forEach(f => console.log("  MAL " + f));
  throw new Error(`${fallos.length} comprobaciones de los sprites fallidas`);
}

console.log(
  "sprites ensamblados correctos: " +
    frames +
    " frames, " +
    ids.length +
    " agentes x " +
    estados.length +
    " estados, " +
    estados.length +
    " animaciones distintas por agente, " +
    PALETA.size +
    " caracteres de paleta, " +
    ritmos.size +
    " ritmos y " +
    gaits.size +
    " formas de andar",
);
"""


def main() -> int:
    for ruta in (RUTA, RUTA_PALETA):
        if not ruta.exists():
            print(f"no existe {ruta}")
            return 1

    texto = RUTA.read_text(encoding="utf-8")
    paleta = claves_de_paleta(RUTA_PALETA.read_text(encoding="utf-8"))
    if len(paleta) < 6:
        print(f"no se ha podido leer la paleta de {RUTA_PALETA}: sale [{' '.join(sorted(paleta))}]")
        return 1

    cuerpo, medias, malos = revisa_filas(texto, paleta)
    malos += revisa_pixel(texto, paleta)
    malos += revisa_manos(texto)

    print(
        f"filas de cuerpo: {len(cuerpo)}  medias filas: {len(medias)}  "
        f"paleta: {' '.join(sorted(paleta))}"
    )
    if malos:
        for que in malos:
            print(f"  MAL {que}")
        print(f"\n{len(malos)} filas, pixeles o manos con la medida equivocada")
        return 1

    if not cuerpo:
        print("no se encontro ningun sprite: revisa la ruta")
        return 1

    print(f"todas las filas miden {CUERPO} px y las medias {MEDIA} px")

    # 3. sprites ensamblados: compilar el módulo y validar cada frame.
    with tempfile.TemporaryDirectory() as tmp:
        destino = pathlib.Path(tmp)
        (destino / "sprites.ts").write_text(texto, encoding="utf-8")
        (destino / "prueba.ts").write_text(PRUEBA.replace("__PALETA__", json.dumps(sorted(paleta))), encoding="utf-8")

        tsc = RAIZ / "frontend" / "node_modules" / ".bin" / ("tsc.cmd" if sys.platform == "win32" else "tsc")
        if not tsc.exists():
            print("falta typescript en frontend/node_modules")
            return 1

        compilar = subprocess.run(
            [str(tsc), "--target", "ES2020", "--module", "ES2020", "--noCheck",
             "--outDir", str(destino / "js"), str(destino / "sprites.ts"), str(destino / "prueba.ts")],
            capture_output=True,
            text=True,
        )
        if compilar.returncode != 0:
            print("el modulo de sprites no compila:")
            print(compilar.stdout or compilar.stderr)
            return 1

        correr = subprocess.run(
            ["node", str(destino / "js" / "prueba.js")],
            capture_output=True,
            text=True,
        )
        if correr.returncode != 0:
            print("los sprites no pasan la revision:")
            print(correr.stdout or correr.stderr)
            return 1

        print(correr.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
