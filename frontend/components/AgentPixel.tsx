"use client";

import { motion, useReducedMotion } from "framer-motion";

/**
 * Agentes pixel-art.
 *
 * Un robot por agente, dibujado con rectángulos (pixel-art real: sin curvas
 * de Nowhere) y con comportamiento propio:
 *
 *  - parpadea a intervalos distintos según el rol (nadie parpadea igual)
 *  - gira la cabeza hacia donde "lee" su panel
 *  - teclea cuando está trabajando, con las manos alternas
 *  - el torso respira siempre: la sala nunca está quieta
 *
 * Todo son keyframes de framer-motion, no CSS, para poder variar la fase por
 * agente y que no se sincronicen (un sala donde todo late a la vez parece
 * unGIF, no un sistema).
 */

export type AgenteId =
  | "wallet"
  | "transaction"
  | "contract"
  | "research"
  | "monitoring"
  | "risk"
  | "explanation";

type Props = {
  id: AgenteId;
  color: string;
  /** 0..1 fuerza del trabajo: controla la velocidad de tecleo y el balanceo */
  carga?: number;
  size?: number;
  alarmed?: boolean;
  className?: string;
};

/** Cada agente tiene su propio ritmo. Nada se mueve igual a nada. */
const PERFIL: Record<AgenteId, { parpadeo: number; balanceo: number; giro: number }> = {
  wallet: { parpadeo: 4.3, balanceo: 3.1, giro: 7.5 },
  transaction: { parpadeo: 3.4, balanceo: 2.2, giro: 5.2 },
  contract: { parpadeo: 5.8, balanceo: 4.4, giro: 9.1 },
  research: { parpadeo: 3.9, balanceo: 2.7, giro: 6.4 },
  monitoring: { parpadeo: 2.6, balanceo: 1.8, giro: 4.6 },
  risk: { parpadeo: 6.2, balanceo: 3.8, giro: 8.3 },
  explanation: { parpadeo: 4.9, balanceo: 2.9, giro: 7.1 },
};

export function AgentPixel({ id, color, carga = 0.6, size = 64, alarmed, className }: Props) {
  const p = PERFIL[id];
  const suave = useReducedMotion();
  const s = size / 64; // el arte está desenhado a 64px de referencia
  const factor = suave ? 0.25 : 1;
  const ritmo = 1 / Math.max(0.25, carga * 1.4);

  return (
    <svg
      width={size}
      height={size * 1.25}
      viewBox="0 0 64 80"
      className={className}
      aria-hidden="true"
    >
      {/* sombra en el suelo: ancla al personaje y da sensación de peso */}
      <ellipse cx={32} cy={76} rx={14} ry={2.5} fill="#0f172a" opacity={0.09} />

      <motion.g
        style={{ originX: "50%", originY: "100%" }}
        animate={{ y: [0, -1.2, 0], rotate: [0, 0.7, 0, -0.7, 0] }}
        transition={{
          duration: p.balanceo * factor,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      >
        {/* piernas: caminan dentro de la estación */}
        <motion.rect
          x={23}
          y={54}
          width={8}
          height={17}
          rx={2}
          fill="#33415580"
          animate={{ y: [54, 52, 54], scaleX: [1, 0.86, 1] }}
          transition={{ duration: ritmo * factor, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.rect
          x={33}
          y={54}
          width={8}
          height={17}
          rx={2}
          fill="#33415580"
          animate={{ y: [54, 52, 54], scaleX: [1, 0.86, 1] }}
          transition={{ duration: ritmo * factor, repeat: Infinity, ease: "easeInOut", delay: 0.12 }}
        />

        {/* torso: respira */}
        <motion.rect
          x={20}
          y={36}
          width={24}
          height={20}
          rx={5}
          fill="#ffffff"
          stroke="#cbd5e1"
          strokeWidth={1.4}
          animate={{ scaleY: [1, 1.045, 1], scaleX: [1, 1.03, 1] }}
          transition={{ duration: 2.6 * factor, repeat: Infinity, ease: "easeInOut" }}
          style={{ originX: "50%", originY: "100%" }}
        />
        {/* placa del agente */}
        <rect x={25} y={41} width={14} height={9} rx={2} fill={color} opacity={0.16} />
        <motion.rect
          x={28}
          y={44}
          width={8}
          height={3}
          rx={1.5}
          fill={color}
          animate={{ opacity: alarmed ? [1, 0.25, 1] : [0.55, 1, 0.55] }}
          transition={{ duration: alarmed ? 1.1 * factor : 2.8 * factor, repeat: Infinity }}
        />

        {/* brazos: tecleo alterno */}
        <motion.rect
          x={12}
          y={39}
          width={7}
          height={15}
          rx={3}
          fill="#ffffff"
          stroke="#cbd5e1"
          strokeWidth={1.3}
          animate={{ y: [39, 46, 39], rotate: [0, -16, 0] }}
          transition={{ duration: ritmo * factor, repeat: Infinity, ease: "easeInOut" }}
          style={{ originX: "80%", originY: "20%" }}
        />
        <motion.rect
          x={45}
          y={39}
          width={7}
          height={15}
          rx={3}
          fill="#ffffff"
          stroke="#cbd5e1"
          strokeWidth={1.3}
          animate={{ y: [39, 46, 39], rotate: [0, 16, 0] }}
          transition={{ duration: ritmo * factor, repeat: Infinity, ease: "easeInOut", delay: ritmo * 0.5 }}
          style={{ originX: "20%", originY: "20%" }}
        />

        {/* cabeza: gira hacia su panel */}
        <motion.g
          style={{ originX: "50%", originY: "90%" }}
          animate={{ rotate: [-5, 5, -5], y: [0, -0.8, 0] }}
          transition={{ duration: p.giro * factor, repeat: Infinity, ease: "easeInOut" }}
        >
          <rect x={20} y={12} width={24} height={24} rx={6} fill="#ffffff" stroke="#cbd5e1" strokeWidth={1.4} />
          {/* antena */}
          <rect x={31} y={5} width={2} height={7} fill="#cbd5e1" />
          <motion.rect
            x={29}
            y={2}
            width={6}
            height={5}
            rx={1.5}
            fill={color}
            animate={{ opacity: [0.4, 1, 0.4] }}
            transition={{ duration: p.parpadeo * factor, repeat: Infinity }}
          />
          {/* visor */}
          <rect x={23} y={18} width={18} height={11} rx={3} fill="#0f172a" />
          {/* ojos: parpadeo */}
          <motion.g
            animate={{ scaleY: [1, 1, 0.12, 1, 1] }}
            transition={{
              duration: p.parpadeo * factor,
              repeat: Infinity,
              times: [0, 0.92, 0.95, 0.98, 1],
            }}
            style={{ originY: "50%" }}
          >
            <rect x={26} y={21} width={4} height={4} rx={1} fill={color} />
            <rect x={34} y={21} width={4} height={4} rx={1} fill={color} />
          </motion.g>
          {alarmed && (
            <motion.rect
              x={39}
              y={15}
              width={4}
              height={4}
              rx={1}
              fill="#dc2626"
              animate={{ opacity: [0, 1, 0] }}
              transition={{ duration: 0.9 * factor, repeat: Infinity }}
            />
          )}
        </motion.g>
      </motion.g>
    </svg>
  );
}

/** Estado "escribiendo" para cabeceras de módulo: tres puntos que laten. */
export function TypingDots({ color = "currentColor", alarmed }: { color?: string; alarmed?: boolean }) {
  return (
    <span className="typing-dots" aria-label={alarmed ? "alerta activa" : "procesando"}>
      {[0, 1, 2].map(i => (
        <motion.span
          key={i}
          animate={{ y: [0, alarmed ? -3 : -2, 0], opacity: [0.35, 1, 0.35] }}
          transition={{ duration: 1.15, repeat: Infinity, delay: i * 0.16, ease: "easeInOut" }}
          style={{ background: alarmed ? "#dc2626" : color }}
        />
      ))}
    </span>
  );
}
