import Link from "next/link";

export default function Landing() {
  return (
    <main id="contenido" className="container landing" style={{ paddingBlock: "3rem 2rem" }}>
      <section aria-labelledby="hero">
        <p className="eyebrow">Ethereum · Base · Agentes de IA</p>
        <h1 id="hero" className="hero-title">
          Inteligencia blockchain que vigila sola
        </h1>
        <p className="lede">
          ChainMind es un sistema multi-agente que analiza wallets, contratos y transacciones.
          Tú eliges una red o pegas una dirección; los agentes perfilan, puntúan el riesgo,
          detectan anomalías y generan el reporte.
        </p>
        <div className="cta-row">
          <Link href="/wallet" className="btn">
            Analizar una wallet
          </Link>
          <Link href="/watch" className="quiet-link">
            Ver vigilancia en vivo →
          </Link>
        </div>
        <dl className="stat-grid" aria-label="Datos del sistema">
          <div className="stat">
            <dt>Redes</dt>
            <dd>2</dd>
          </div>
          <div className="stat">
            <dt>Agentes</dt>
            <dd>7</dd>
          </div>
          <div className="stat">
            <dt>Reporte en</dt>
            <dd>&lt;10 s</dd>
          </div>
        </dl>
      </section>

      <hr className="rule" />

      <section aria-labelledby="para-que">
        <h2 id="para-que">Para qué sirve</h2>
        <ul className="def-list">
          <li>
            <strong>Verificar antes de enviar</strong>
            <p>Pega la dirección de una contraparte y descubre mezcladores o patrones de bot.</p>
          </li>
          <li>
            <strong>Auditar contratos</strong>
            <p>Permisos peligrosos — mint privilegiado, blacklist, DELEGATECALL — antes de firmar.</p>
          </li>
          <li>
            <strong>Vigilar la red</strong>
            <p>Cada transacción de los últimos bloques, puntuada y con alertas automáticas.</p>
          </li>
          <li>
            <strong>Documentar casos</strong>
            <p>Reporte descargable con perfil, riesgo, rutas de fondos y explicación.</p>
          </li>
        </ul>
      </section>

      <hr className="rule" />

      <section aria-labelledby="como-se-usa">
        <h2 id="como-se-usa">Cómo se usa</h2>
        <ol className="steps">
          <li>
            <div>
              <strong>Elige red y objetivo</strong>
              <p style={{ margin: "0.25rem 0 0", color: "var(--muted)" }}>
                En <Link href="/wallet">Wallet</Link> pega una dirección 0x. En{" "}
                <Link href="/watch">Vigilancia</Link> basta elegir la red.
              </p>
            </div>
          </li>
          <li>
            <div>
              <strong>Lee el score</strong>
              <p style={{ margin: "0.25rem 0 0", color: "var(--muted)" }}>
                0–29 bajo · 30–69 medio · 70–100 alto. Cada factor, explicado en claro.
              </p>
            </div>
          </li>
          <li>
            <div>
              <strong>Profundiza o descarga</strong>
              <p style={{ margin: "0.25rem 0 0", color: "var(--muted)" }}>
                Traza fondos, audita el <Link href="/contract">contrato</Link> o descarga el .md.
              </p>
            </div>
          </li>
        </ol>
        <p style={{ color: "var(--muted)", fontSize: "0.875rem" }}>
          Requiere el backend en <span className="mono">:8000</span>. Sin claves funciona con
          fuentes públicas; con <span className="mono">ANTHROPIC_API_KEY</span> redacta Claude.
        </p>
      </section>

      <hr className="rule" />

      <section aria-labelledby="agentes">
        <h2 id="agentes">Agentes</h2>
        <ul className="mini-grid">
          <li><strong>Wallet Intelligence</strong>Perfil y patrón horario.</li>
          <li><strong>Risk Scoring</strong>Heurísticas, sin ML.</li>
          <li><strong>Explanation</strong>El único con LLM.</li>
          <li><strong>Smart Contract</strong>Bytecode + Slither.</li>
          <li><strong>Anomaly</strong>Isolation Forest nocturno.</li>
          <li><strong>Investigation</strong>Rutas de fondos.</li>
        </ul>
      </section>
    </main>
  );
}
