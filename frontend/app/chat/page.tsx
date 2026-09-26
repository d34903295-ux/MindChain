"use client";

import { API_BASE } from "../../lib/api";
import { useEffect, useRef, useState } from "react";
import ChatDatos from "../../components/ChatGrafico";

type Msg = {
  rol: "user" | "bot";
  texto: string;
  herramienta?: string | null;
  enrutado?: string | null;
  fuente?: string;
  modelo?: string;
  motivo?: string;
  ms?: number;
  datos?: Record<string, unknown> | null;
};

const EJEMPLOS = [
  "¿Qué wallet se movió más en los últimos 5 bloques?",
  "Dame un resumen de la actividad en base",
  "Compara 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 y 0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
  "¿Qué pasa en el feed de ethereum?",
  "Analiza 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 en base",
  "¿Qué wallets vigilamos?",
  "¿Cómo va el sistema?",
];

export default function ChatPage() {
  const [mensajes, setMensajes] = useState<Msg[]>([]);
  const [texto, setTexto] = useState("");
  const [pensando, setPensando] = useState(false);
  const [error, setError] = useState("");
  const finRef = useRef<HTMLDivElement>(null);
  const preguntaDeUrl = useRef(false);

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [mensajes, pensando]);

  async function preguntar(pregunta: string) {
    if (!pregunta || pensando) return;
    setError("");
    setTexto("");
    setMensajes(m => [...m, { rol: "user", texto: pregunta }]);
    setPensando(true);
    const t0 = performance.now();
    try {
      const historial = mensajes
        .filter(m => m.rol === "user" || m.rol === "bot")
        .slice(-6)
        .map(m => ({ role: m.rol === "user" ? "user" : "assistant", content: m.texto }));
      const r = await fetch("${API_BASE}/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mensaje: pregunta, historial }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || `el backend devolvió ${r.status}`);
      setMensajes(m => [
        ...m,
        {
          rol: "bot",
          texto: j.respuesta,
          herramienta: j.herramienta,
          enrutado: j.enrutado,
          fuente: j.source,
          modelo: j.modelo,
          motivo: j.motivo,
          ms: Math.round(performance.now() - t0),
          datos: j.datos ?? null,
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPensando(false);
    }
  }

  // /chat?q=… deja la pregunta escrita y ejecutada al abrir: sirve para
  // compartir un análisis concreto y para comprobar la pantalla sin teclear.
  useEffect(() => {
    if (preguntaDeUrl.current) return;
    preguntaDeUrl.current = true;
    const q = new URLSearchParams(window.location.search).get("q");
    if (q) void preguntar(q);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    await preguntar(texto.trim());
  }

  return (
    <main id="contenido" className="container page">
      <header className="page-head">
        <p className="eyebrow">Nodo de chat</p>
        <h1 className="page-title">Pregunta al sistema</h1>
        <p className="section-lede">
          Usa los mismos agentes y las mismas fuentes que el resto de ChainMind. Si le pides una
          wallet, un contrato o una ruta de fondos, los datos son reales y están calculados aquí,
          no inventados. También sabe ranking de actividad, resumen de la cadena y comparativa
          entre wallets: cuando la respuesta trae números, los dibuja.
        </p>
      </header>

      <div className="chat-shell" role="log" aria-live="polite" aria-label="Conversación">
        {mensajes.length === 0 && (
          <div className="chat-vacio">
            <p>Pregúntame por una wallet, un contrato, el feed, el centinela o la watchlist.</p>
            <ul className="chat-ejemplos">
              {EJEMPLOS.map(ej => (
                <li key={ej}>
                  <button type="button" className="chat-chip" onClick={() => setTexto(ej)}>
                    {ej}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {mensajes.map((m, i) => (
          <div key={i}
            className={`chat-burbuja ${m.rol === "user" ? "user" : "bot"}${m.datos ? " wide" : ""}`}>
            <p className="chat-texto">{m.texto}</p>
            {m.rol === "bot" && <ChatDatos datos={m.datos} />}
            {m.rol === "bot" && (
              <p className="chat-meta">
                {m.herramienta ? `herramienta: ${m.herramienta}` : "sin herramienta"}
                {m.herramienta && m.enrutado ? ` (elegida por ${m.enrutado})` : ""}
                {m.fuente === "llm" && m.modelo ? ` · ${m.modelo}` : " · texto determinista"}
                {m.ms ? ` · ${(m.ms / 1000).toFixed(1)}s` : ""}
                {m.fuente === "determinista" && m.motivo ? ` · ${m.motivo}` : ""}
              </p>
            )}
          </div>
        ))}

        {pensando && (
          <div className="chat-burbuja bot">
            <p className="chat-texto chat-pensando">
              Consultando los agentes<span className="puntos">…</span>
            </p>
          </div>
        )}
        <div ref={finRef} />
      </div>

      {error && (
        <p role="alert" className="error-text">
          {error}
        </p>
      )}

      <form onSubmit={enviar} className="chat-form" aria-label="Escribir mensaje">
        <label htmlFor="chat-input" className="sr-only">
          Tu pregunta
        </label>
        <input
          id="chat-input"
          className="input"
          placeholder="Analiza 0x…, dime qué wallet se movió más o compara dos"
          value={texto}
          onChange={e => setTexto(e.target.value)}
          autoComplete="off"
          maxLength={2000}
        />
        <button type="submit" className="btn" disabled={!texto.trim() || pensando}>
          {pensando ? "Pensando…" : "Enviar"}
        </button>
      </form>
    </main>
  );
}
