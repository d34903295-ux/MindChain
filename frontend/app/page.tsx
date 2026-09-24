import Link from "next/link";

export default function Landing() {
  return (
    <main id="contenido" className="container" style={{ paddingBlock: "2rem" }}>
      <section aria-labelledby="hero">
        <p
          style={{
            display: "inline-block",
            fontSize: "0.8125rem",
            fontWeight: 700,
            color: "var(--ok)",
            background: "var(--ok-bg)",
            border: "1px solid var(--ok-border)",
            borderRadius: "999px",
            padding: "0.2rem 0.75rem",
          }}
        >
          Ethereum · Base · en vivo
        </p>
        <h1 id="hero" style={{ fontSize: "clamp(2rem, 1.4rem + 3vw, 3rem)", lineHeight: 1.15, marginBlockEnd: "0.5rem" }}>
          Inteligencia blockchain con agentes de IA que vigilan solos
        </h1>
        <p style={{ fontSize: "1.125rem", color: "var(--muted)", maxWidth: "44rem" }}>
          <strong>Qué es:</strong> ChainMind es un sistema multi-agente que analiza wallets, contratos
          y transacciones en Ethereum y Base. Tú eliges una red o pegas una dirección; los agentes
          hacen el resto: perfilan, puntúan el riesgo, detectan anomalías y generan el reporte.
        </p>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", marginBlockStart: "1.25rem" }}>
          <Link href="/wallet" className="btn">
            Analizar una wallet
          </Link>
          <Link href="/watch" className="btn btn-secondary">
            Ver vigilancia en vivo
          </Link>
          <Link href="/contract" className="btn btn-secondary">
            Auditar un contrato
          </Link>
        </div>
        <dl className="stat-grid" aria-label="Datos del sistema">
          <div className="stat">
            <dt>Redes vigiladas</dt>
            <dd>2 (Ethereum, Base)</dd>
          </div>
          <div className="stat">
            <dt>Agentes de IA</dt>
            <dd>7</dd>
          </div>
          <div className="stat">
            <dt>Reporte completo en</dt>
            <dd>&lt;10 segundos</dd>
          </div>
        </dl>
      </section>

      <section aria-labelledby="para-que" className="card">
        <h2 id="para-que">¿Para qué sirve?</h2>
        <ul style={{ paddingInlineStart: "1.125rem", margin: 0 }}>
          <li>
            <strong>Verificar antes de enviar:</strong> pega la dirección de una contraparte y descubre
            si interactuó con mezcladores o muestra patrones de bot.
          </li>
          <li>
            <strong>Auditar contratos:</strong> detecta permisos peligrosos (mint privilegiado,
            blacklist, pausa centralizada, DELEGATECALL, SELFDESTRUCT) antes de interactuar.
          </li>
          <li>
            <strong>Vigilar la red:</strong> el panel en vivo puntúa cada transacción de los últimos
            bloques y levanta alertas solo.
          </li>
          <li>
            <strong>Documentar casos:</strong> descarga el reporte en Markdown con perfil, riesgo,
            rutas de fondos y explicación.
          </li>
        </ul>
      </section>

      <section aria-labelledby="como-se-usa" className="card">
        <h2 id="como-se-usa">¿Cómo se usa?</h2>
        <ol style={{ paddingInlineStart: "1.25rem", margin: 0 }}>
          <li>
            <strong>Elige red y objetivo:</strong> en <Link href="/wallet">Wallet</Link> selecciona
            Ethereum o Base y pega una dirección 0x. En <Link href="/watch">Vigilancia</Link> solo
            elige la red: los agentes ya están mirando cada transacción.
          </li>
          <li>
            <strong>Lee el score y la explicación:</strong> 0–29 bajo, 30–69 medio, 70–100 alto.
            Cada factor de riesgo viene explicado en lenguaje claro, con QR de la dirección para
            compartirla o escanearla.
          </li>
          <li>
            <strong>Profundiza o descarga:</strong> traza rutas de fondos, audita el contrato en{" "}
            <Link href="/contract">Contrato</Link> o descarga el reporte .md del caso.
          </li>
        </ol>
        <p style={{ color: "var(--muted)", fontSize: "0.875rem" }}>
          Requisito: el backend debe estar en <span className="mono">http://localhost:8000</span> y
          esta app en <span className="mono">http://localhost:3000</span>. Sin claves de API funciona
          con fuentes públicas; con <span className="mono">ANTHROPIC_API_KEY</span> las explicaciones
          las redacta Claude.
        </p>
      </section>

      <section aria-labelledby="agentes" className="card">
        <h2 id="agentes">Los 7 agentes</h2>
        <ul style={{ paddingInlineStart: "1.125rem", margin: 0 }}>
          <li><strong>Wallet Intelligence:</strong> antigüedad, transacciones, contrapartes y patrón horario (humano vs. bot).</li>
          <li><strong>Risk Scoring:</strong> heurísticas sin ML: mezcladores, wallet nueva, concentración de fondos, balance alto y joven.</li>
          <li><strong>Explanation:</strong> el único que llama al LLM; traduce el score a lenguaje humano.</li>
          <li><strong>Smart Contract:</strong> disassembler EVM + heurísticas de permisos + Slither opcional.</li>
          <li><strong>Anomaly Detection:</strong> Isolation Forest en batch nocturno sobre frecuencia, montos y gas.</li>
          <li><strong>Investigation:</strong> trazado de rutas de fondos (BFS + Cypher en Neo4j).</li>
          <li><strong>Report:</strong> reporte descargable del caso.</li>
        </ul>
      </section>
    </main>
  );
}
