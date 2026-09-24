import Link from "next/link";
import { LiveTicker } from "../components/LiveTicker";

const SAMPLE = [
  { hash: "0x9fd170…f31f7d", value: "0.42 ETH", score: 5, tone: "var(--ok)", flags: "limpia" },
  { hash: "0x8f622d…068ea", value: "1,240.00 ETH", score: 45, tone: "var(--warn)", flags: "ballena · outlier 20× mediana" },
  { hash: "0x1ca171…b074d2", value: "0.00 ETH", score: 65, tone: "var(--bad)", flags: "mezclador conocido" },
  { hash: "0xb42da2…fe79cf", value: "3.18 ETH", score: 5, tone: "var(--ok)", flags: "creación de contrato" },
];

export default function Landing() {
  return (
    <main id="contenido">
      <div className="landing-wide">
        <div className="hero-grid">
          <section aria-labelledby="hero">
            <p className="eyebrow">Ethereum · Base · Agentes de IA</p>
            <h1 id="hero" className="hero-title-xl">
              La cadena habla.
              <br />
              Nosotros <span className="accent">la vigilamos.</span>
            </h1>
            <p className="lede">
              ChainMind analiza cada wallet, contrato y transacción con 7 agentes de IA.
              Tú eliges la red; ellos detectan el riesgo y te lo explican en claro.
            </p>
            <div className="cta-row">
              <Link href="/wallet" className="btn">
                Analizar una wallet
              </Link>
              <Link href="/watch" className="quiet-link">
                Ver vigilancia en vivo →
              </Link>
            </div>
            <LiveTicker />
          </section>

          <figure
            className="terminal"
            aria-label="Ejemplo de transacciones analizadas por los agentes"
            style={{ margin: 0 }}
          >
            <div className="terminal-bar" aria-hidden="true">
              <i />
              <i />
              <i />
              <span style={{ marginInlineStart: "0.5rem" }}>chainmind — feed en vivo</span>
            </div>
            {SAMPLE.map(s => (
              <div className="terminal-row" key={s.hash}>
                <span>{s.hash}</span>
                <span>
                  {s.value} ·{" "}
                  <span className="score-num" style={{ color: s.tone }}>
                    {s.score}
                  </span>
                </span>
                <span className="flags">{s.flags}</span>
              </div>
            ))}
            <figcaption
              style={{ padding: "0.625rem 1rem", borderBlockStart: "1px solid var(--border)", fontSize: "0.75rem", color: "var(--muted)" }}
            >
              Vista previa con datos de ejemplo — los datos reales están en{" "}
              <Link href="/watch">Vigilancia</Link>.
            </figcaption>
          </figure>
        </div>
      </div>

      <div className="landing-wide">
        <section className="landing-section" aria-labelledby="dolor">
          <h2 id="dolor" className="eyebrow">
            El problema
          </h2>
          <p style={{ fontSize: "clamp(1.25rem, 1rem + 1.5vw, 1.75rem)", lineHeight: 1.3, maxWidth: "40rem" }}>
            Cada día se mueven millones sin contexto. Una dirección es solo un hash hasta que
            alguien la investiga — y casi nadie tiene tiempo de hacerlo.
          </p>
        </section>

        <section className="landing-section" aria-labelledby="beneficios">
          <h2 id="beneficios" className="eyebrow">
            Qué obtienes
          </h2>
          <ul className="benefit-grid">
            <li>
              <strong>Verificar antes de enviar</strong>
              <p>Contraparte con mezcladores o bots, visible en segundos.</p>
            </li>
            <li>
              <strong>Auditar contratos</strong>
              <p>Mint privilegiado, blacklist, DELEGATECALL — antes de firmar.</p>
            </li>
            <li>
              <strong>Vigilancia autónoma</strong>
              <p>Cada transacción puntuada sola, alertas sin que pidas nada.</p>
            </li>
            <li>
              <strong>Casos documentados</strong>
              <p>Reporte descargable: perfil, riesgo, rutas y explicación.</p>
            </li>
          </ul>
        </section>

        <section className="landing-section faq" aria-labelledby="faq">
          <h2 id="faq" className="eyebrow">
            Preguntas
          </h2>
          <details>
            <summary>¿Necesito API keys o una cuenta?</summary>
            <p>No. Funciona con fuentes públicas. Con ANTHROPIC_API_KEY, Claude redacta las explicaciones.</p>
          </details>
          <details>
            <summary>¿Qué redes soporta?</summary>
            <p>Ethereum y Base, con el mismo motor de agentes. Arbitrum llega añadiendo una entrada al registro.</p>
          </details>
          <details>
            <summary>¿Un score alto es una acusación?</summary>
            <p>No. Es un heurístico automatizado: una señal para investigar on-chain, no un veredicto.</p>
          </details>
          <details>
            <summary>¿Cómo se usa?</summary>
            <p>
              En <Link href="/wallet">Wallet</Link> pega una dirección 0x. En{" "}
              <Link href="/watch">Vigilancia</Link> elige la red y mira. En{" "}
              <Link href="/contract">Contrato</Link> audita código verificado.
            </p>
          </details>
        </section>

        <section className="final-cta" aria-labelledby="cta">
          <h2 id="cta">
            Pega una dirección.
            <br />
            Entiende el riesgo.
          </h2>
          <Link href="/wallet" className="btn">
            Analizar una wallet
          </Link>
        </section>
      </div>
    </main>
  );
}
