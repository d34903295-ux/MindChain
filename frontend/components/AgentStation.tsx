"use client";

import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { AgentPixel, TypingDots, type AgenteId } from "./AgentPixel";

/**
 * Estación operativa de un agente.
 *
 * Reemplaza a la tarjeta estática: cada estación tiene su robot trabajando,
 * su barra de progreso viva, tres métricas de su propio rol y un log que
 * escribe en el tiempo. Los valores vienen del feed y del estado del sistema,
 * no de números inventados.
 */

export type StationData = {
  titulo: string;
  estado: string;
  /** 0..1 progreso medido. `null` = sin señal real: barra indeterminada, no un porcentaje inventado. */
  progreso: number | null;
  metricas: [string, string][];
  lineas: string[];
  alerta?: boolean;
};

type Props = {
  id: AgenteId;
  data: StationData;
  color: string;
  compact?: boolean;
};

export function AgentStation({ id, data, color, compact }: Props) {
  const suave = useReducedMotion();
  const [linea, setLinea] = useState(0);

  useEffect(() => {
    if (data.lineas.length <= 1) return;
    const id2 = setInterval(() => setLinea(l => (l + 1) % data.lineas.length), 3400);
    return () => clearInterval(id2);
  }, [data.lineas.length]);

  const medido = data.progreso !== null;

  return (
    <motion.section
      className={data.alerta ? "station is-alert" : "station"}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.2, 0.7, 0.2, 1] }}
      style={{ ["--agent-color" as string]: color }}
    >
      <header className="station-head">
        <div className="station-avatar">
          <AgentPixel
            id={id}
            color={color}
            carga={medido ? 0.45 + (data.progreso ?? 0) * 0.6 : 0.35}
            size={42}
            alarmed={data.alerta}
          />
        </div>
        <div className="station-id">
          <h3>{data.titulo}</h3>
          <p className="station-state">
            <TypingDots color={color} alarmed={data.alerta} />
            {data.estado}
          </p>
        </div>
        <span className={data.alerta ? "station-dot is-alert" : "station-dot"} aria-hidden="true" />
      </header>

      {medido ? (
        <div
          className="station-bar"
          role="progressbar"
          aria-valuenow={Math.round((data.progreso ?? 0) * 100)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${data.titulo}: ${data.estado}`}
        >
          <motion.span
            className={data.alerta ? "fill is-alert" : "fill"}
            animate={{ width: `${Math.max(4, Math.min(100, (data.progreso ?? 0) * 100))}%` }}
            transition={{ duration: 0.8, ease: "easeOut" }}
          />
        </div>
      ) : (
        // sin señal medible no se inventa un porcentaje: se muestra que está activo
        <div className="station-bar is-indeterminate" aria-hidden="true">
          <motion.span
            className="fill"
            animate={suave ? {} : { x: ["-30%", "130%"] }}
            transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
          />
        </div>
      )}

      <dl className="station-metrics">
        {data.metricas.map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd className="mono" title={`${k}: ${v}`}>{v}</dd>
          </div>
        ))}
      </dl>

      {data.lineas.length > 0 && (
        <motion.p
          key={linea}
          className={data.alerta ? "station-log is-alert" : "station-log"}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
        >
          <span className="station-log-tick" aria-hidden="true" />
          {data.lineas[linea]}
        </motion.p>
      )}
    </motion.section>
  );
}

/** Micrográfico de barras/área: el pulso visual de cada agente. */
export function Sparkline({
  valores,
  color,
  alto = 34,
}: {
  valores: number[];
  color: string;
  alto?: number;
}) {
  const suave = useReducedMotion();
  const max = Math.max(1, ...valores);
  const puntos = valores
    .map((v, i) => `${(i / Math.max(1, valores.length - 1)) * 100},${alto - (v / max) * (alto - 4) - 2}`)
    .join(" ");
  const ultimo = valores[valores.length - 1] ?? 0;

  return (
    <svg viewBox={`0 0 100 ${alto}`} preserveAspectRatio="none" className="spark" aria-hidden="true">
      <polyline
        points={puntos}
        fill="none"
        stroke={color}
        strokeWidth={1.6}
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
        opacity={0.85}
      />
      <motion.circle
        r={2.4}
        fill={color}
        animate={suave ? {} : { cx: [96, 98, 96], opacity: [0.4, 1, 0.4] }}
        transition={{ duration: 2.4, repeat: Infinity }}
        cy={alto - (ultimo / max) * (alto - 4) - 2}
        cx={98}
      />
    </svg>
  );
}

/** Medidor de semicírculo para el score: el Risk Agent siempre visible. */
export function ScoreDial({ valor, alerta }: { valor: number | null; alerta?: boolean }) {
  const suave = useReducedMotion();
  const r = 26;
  const circ = Math.PI * r;
  const v = valor ?? 0;
  const tono = alerta || (valor ?? 0) >= 70 ? "#dc2626" : (valor ?? 0) >= 30 ? "#b45309" : "#15803d";
  return (
    <div className="dial" role="img" aria-label={valor === null ? "score no disponible" : `score ${valor} de 100`}>
      <svg viewBox="0 0 64 38" width={72} height={44}>
        <path d="M6 34 A26 26 0 0 1 58 34" fill="none" stroke="#e2e8f0" strokeWidth={5} strokeLinecap="round" />
        <motion.path
          d="M6 34 A26 26 0 0 1 58 34"
          fill="none"
          stroke={tono}
          strokeWidth={5}
          strokeLinecap="round"
          strokeDasharray={circ}
          initial={{ strokeDashoffset: circ }}
          animate={{ strokeDashoffset: circ * (1 - v / 100) }}
          transition={{ duration: 1.1, ease: "easeOut" }}
        />
      </svg>
      <span className="dial-value mono">
        {valor === null ? "n/d" : valor}
        {valor !== null && <small>/100</small>}
      </span>
    </div>
  );
}
