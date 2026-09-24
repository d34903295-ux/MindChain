"use client";

import { useEffect, useRef, useState } from "react";

type Msg = {
  rol: "user" | "bot";
  texto: string;
  herramienta?: string | null;
  fuente?: string;
  modelo?: string;
  motivo?: string;
  ms?: number;
};

const EJEMPLOS = [
  "¿Cómo va el sistema?",
  "Analiza 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 en base",
  "¿Qué pasa en el feed de ethereum?",
  "¿Qué wallets vigilamos?",
];

export default function ChatPage() {
  const [mensajes, setMensajes] = useState<Msg[]>([]);
  const [texto, setTexto] = useState("");
  const [pensando, setPensando] = useState(false);
  const [error, setError] = useState("");
  const finRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [mensajes, pensando]);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    const pregunta = texto.trim();
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
      const r = await fetch("http://localhost:8000/chat", {
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
          fuente: j.source,
          modelo: j.modelo,
          motivo: j.motivo,
          ms: Math.round(performance.now() - t0),
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPensando(false);
    }
  }

  return (
    <main id="contenido" className="container page">
      <header className="page-head">
        <p className="eyebrow">Nodo de chat</p>
        <h1 className="page-title">Pregunta al sistema</h1>
        <p className="section-lede">
          Usa los mismos agentes y las mismas fuentes que el resto de ChainMind. Si le pides una
          wallet, un contrato o una ruta de fondos, los datos son reales y están calculados aquí,
          no inventados.
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
          <div key={i} className={m.rol === "user" ? "chat-burbuja user" : "chat-burbuja bot"}>
            <p className="chat-texto">{m.texto}</p>
            {m.rol === "bot" && (
              <p className="chat-meta">
                {m.herramienta ? `herramienta: ${m.herramienta}` : "sin herramienta"}
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
          placeholder="Analiza 0x… o pregúntame por el sistema"
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
