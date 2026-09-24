"use client";

import { useEffect, useState } from "react";

/** Prueba en vivo: último bloque de Ethereum analizado por los agentes. */
export function LiveTicker() {
  const [text, setText] = useState("conectando con la red…");

  useEffect(() => {
    let alive = true;
    fetch("http://localhost:8000/feed/ethereum?max_blocks=1")
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then(j => {
        if (alive) setText(`bloque ${j.latest} · ${j.n_txs} txs analizadas · ${j.n_alerts} alertas`);
      })
      .catch(() => {
        if (alive) setText("7 agentes · 2 redes · reportes <10 s");
      });
    return () => {
      alive = false;
    };
  }, []);

  return (
    <p className="ticker" aria-live="polite">
      <span className="dot" aria-hidden="true" />
      {text}
    </p>
  );
}
