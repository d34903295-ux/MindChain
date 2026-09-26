"use client";

/**
 * Lo que el chat dibuja cuando una herramienta devuelve datos, no texto.
 *
 * Nada de librerías: un SVG de 40 líneas no merece 300 kB de dependencias, y
 * este proyecto es local por diseño. Todas las series llegan del backend
 * (`datos.serie`); aquí solo se pintan.
 */

export type PuntoBloque = {
  bloque: number;
  transacciones: number;
  volumen_eth: number;
  direcciones: number;
  alertas: number;
};

export type FilaRanking = {
  direccion: string;
  movimientos: number;
  envios: number;
  recibido_eth: number;
  enviado_eth: number;
  total_eth: number;
  contrapartes: number;
  bloques_activos: number;
  alertas: number;
  score_max: number;
};

export type FilaComparativa = {
  direccion: string;
  score: number | null;
  nivel: string;
  transacciones: number | null;
  contrapartes: number | null;
  balance_usd: number | null;
  confianza_muestra: string | null;
  factores: string[];
  calidad_datos: boolean;
};

type SerieComparativa = {
  etiquetas: string[];
  scores: (number | null)[];
  transacciones: (number | null)[];
  niveles: string[];
};

const corta = (a: string) => (a.length > 12 ? `${a.slice(0, 6)}…${a.slice(-4)}` : a);

const num = (v: number | null | undefined, dec = 0) =>
  v === null || v === undefined || Number.isNaN(v)
    ? "—"
    : v.toLocaleString("es-ES", { maximumFractionDigits: dec });

/** Barras por bloque. La altura es siempre relativa al máximo del rango. */
export function GraficoSerie({ serie }: { serie: PuntoBloque[] }) {
  if (!serie?.length) return null;
  const max = Math.max(1, ...serie.map(p => p.transacciones));
  const maxEth = Math.max(1e-9, ...serie.map(p => p.volumen_eth));
  const primero = serie[0].bloque;
  const ultimo = serie[serie.length - 1].bloque;

  return (
    <figure className="graf">
      <figcaption className="graf-cap">
        Actividad por bloque · {primero}–{ultimo}
      </figcaption>
      <div className="graf-bars" role="img"
        aria-label={`Transacciones por bloque entre ${primero} y ${ultimo}. Máximo ${max} transacciones en un bloque.`}>
        {serie.map(p => {
          const alto = Math.max(3, Math.round((p.transacciones / max) * 100));
          return (
            <div className="graf-col" key={p.bloque}
              title={`bloque ${p.bloque}: ${p.transacciones} tx · ${num(p.volumen_eth, 2)} ETH · ${p.direcciones} direcciones${p.alertas ? ` · ${p.alertas} alertas` : ""}`}>
              <span className="graf-bar" style={{ height: `${alto}%` }} />
              {p.alertas > 0 && <span className="graf-alerta" aria-hidden="true" />}
            </div>
          );
        })}
      </div>
      <div className="graf-eje">
        <span>{primero}</span>
        <span>máx {max} tx/bloque</span>
        <span>{ultimo}</span>
      </div>
      <p className="graf-nota">
        Volumen: {serie.map(p => `${p.bloque} → ${num(p.volumen_eth, 2)} ETH`).join(" · ")}
        {maxEth > 0 ? ` · pico ${num(maxEth, 2)} ETH` : ""}
      </p>
    </figure>
  );
}

/** Comparativa de wallets: una barra por dirección, en el mismo eje. */
export function GraficoComparativa({ serie }: { serie: SerieComparativa }) {
  if (!serie?.etiquetas?.length) return null;
  const conScore = serie.scores.filter((s): s is number => typeof s === "number");
  if (!conScore.length) return null;
  const max = Math.max(1, ...conScore);
  return (
    <figure className="graf">
      <figcaption className="graf-cap">Riesgo comparado (score / 100)</figcaption>
      <div className="graf-hbars" role="img"
        aria-label={`Scores de riesgo: ${serie.etiquetas.map((e, i) => `${e} ${num(serie.scores[i])}`).join(", ")}`}>
        {serie.etiquetas.map((etiqueta, i) => {
          const s = serie.scores[i];
          return (
            <div className="graf-hrow" key={etiqueta}>
              <span className="graf-hlabel">{etiqueta}</span>
              <span className="graf-htrack">
                <span
                  className={`graf-hfill ${typeof s === "number" && s >= 70 ? "alto" : typeof s === "number" && s >= 30 ? "medio" : "bajo"}`}
                  style={{ width: `${typeof s === "number" ? Math.max(2, (s / max) * 100) : 0}%` }}
                />
              </span>
              <span className="graf-hval">{num(s)}</span>
            </div>
          );
        })}
      </div>
    </figure>
  );
}

export function TablaRanking({ ranking }: { ranking: FilaRanking[] }) {
  if (!ranking?.length) return null;
  return (
    <div className="table-wrap">
      <table className="tabla-ranking">
        <caption className="sr-only">Direcciones ordenadas por número de movimientos</caption>
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col">dirección</th>
            <th scope="col" className="num">movs</th>
            <th scope="col" className="num">envía</th>
            <th scope="col" className="num">recibe</th>
            <th scope="col" className="num">contrapartes</th>
            <th scope="col" className="num">bloques</th>
          </tr>
        </thead>
        <tbody>
          {ranking.map((f, i) => (
            <tr key={f.direccion} className={i === 0 ? "es-top" : undefined}>
              <td>{i + 1}</td>
              <th scope="row">
                <code title={f.direccion}>{corta(f.direccion)}</code>
                {i === 0 && <span className="graf-tag">más activa</span>}
              </th>
              <td className="num">{num(f.movimientos)}</td>
              <td className="num">{num(f.enviado_eth, 2)}</td>
              <td className="num">{num(f.recibido_eth, 2)}</td>
              <td className="num">{num(f.contrapartes)}</td>
              <td className="num">{num(f.bloques_activos)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function TablaComparativa({ tabla }: { tabla: FilaComparativa[] }) {
  if (!tabla?.length) return null;
  return (
    <div className="table-wrap">
      <table className="tabla-ranking">
        <caption className="sr-only">Comparativa de wallets</caption>
        <thead>
          <tr>
            <th scope="col">dirección</th>
            <th scope="col" className="num">score</th>
            <th scope="col">nivel</th>
            <th scope="col" className="num">transacciones</th>
            <th scope="col" className="num">contrapartes</th>
            <th scope="col" className="num">balance USD</th>
            <th scope="col">muestra</th>
          </tr>
        </thead>
        <tbody>
          {tabla.map(f => (
            <tr key={f.direccion}>
              <th scope="row"><code title={f.direccion}>{corta(f.direccion)}</code></th>
              <td className="num">{num(f.score)}</td>
              <td>
                <span className={`pill ${f.nivel === "alto" ? "is-bad" : f.nivel === "medio" ? "is-warn" : "is-ok"}`}>
                  {f.nivel}
                </span>
              </td>
              <td className="num">{num(f.transacciones)}</td>
              <td className="num">{num(f.contrapartes)}</td>
              <td className="num">{num(f.balance_usd, 2)}</td>
              <td className="muestra">{f.confianza_muestra ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {tabla.some(f => f.calidad_datos) && (
        <p className="data-warning">Alguna fila viene con datos degradados: el proveedor no devolvió todo.</p>
      )}
    </div>
  );
}

/** Elige qué pintar según lo que devolvió la herramienta. */
export default function ChatDatos({
  datos,
}: {
  datos: Record<string, unknown> | null | undefined;
}) {
  if (!datos || typeof datos !== "object") return null;
  const serie = datos.serie as PuntoBloque[] | undefined;
  const serieComp = datos.serie as unknown as SerieComparativa | undefined;
  const ranking = datos.ranking as FilaRanking[] | undefined;
  const tabla = datos.tabla as FilaComparativa[] | undefined;
  const esSerieBloques = Array.isArray(serie) && serie.length > 0 && typeof serie[0]?.bloque === "number";
  const esComparativa = !esSerieBloques && !!serieComp && Array.isArray(serieComp.etiquetas);
  if (!esSerieBloques && !esComparativa && !ranking?.length && !tabla?.length) return null;

  return (
    <div className="chat-datos">
      {esSerieBloques && <GraficoSerie serie={serie as PuntoBloque[]} />}
      {esComparativa && <GraficoComparativa serie={serieComp as SerieComparativa} />}
      {!!ranking?.length && <TablaRanking ranking={ranking} />}
      {!!tabla?.length && <TablaComparativa tabla={tabla} />}
    </div>
  );
}
