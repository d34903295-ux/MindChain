import Link from "next/link";
import { LiveTerminal } from "../components/LiveTerminal";
import { Reveal } from "../components/Reveal";

export default function Landing() {
  return (
    <main id="contenido">
      <div className="landing-wide">
        <div className="hero-grid">
          <section aria-labelledby="hero">
            <p className="eyebrow hero-enter">Ethereum · Base · 7 agentes de IA</p>
            <h1 id="hero" className="hero-title-xl hero-enter hero-enter-1">
              La cadena habla.
              <br />
              Nosotros <span className="accent">la vigilamos.</span>
            </h1>
            <p className="lede hero-enter hero-enter-2">
              ChainMind analiza cada wallet, contrato y transacción. Tú eliges la red;
              los agentes detectan el riesgo y te lo explican en claro.
            </p>
            <div className="cta-row hero-enter hero-enter-3">
              <Link href="/wallet" className="btn">
                Analizar una wallet
              </Link>
              <Link href="/watch" className="quiet-link">
                Ver vigilancia en vivo →
              </Link>
            </div>
            <div className="hero-enter hero-enter-4">
              <LiveTerminal />
            </div>
          </section>

          <div className="hero-enter hero-enter-2" style={{ display: "grid", gap: "0.75rem", alignContent: "center" }}>
            <dl className="stat-grid" aria-label="Datos del sistema" style={{ marginBlockStart: 0 }}>
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
              <div className="stat">
                <dt>Tests</dt>
                <dd>53/53</dd>
              </div>
            </dl>
            <p style={{ color: "var(--muted)", fontSize: "0.9375rem", margin: 0 }}>
              Sin cuentas ni claves para empezar. Heurísticas y ML clásico primero; el LLM
              solo redacta explicaciones. Análisis on-demand, sin vender tus datos.
            </p>
          </div>
        </div>
      </div>

      <div className="landing-wide">
        <Reveal label="El problema">
          <h2 className="eyebrow">El problema</h2>
          <p style={{ fontSize: "clamp(1.25rem, 1rem + 1.5vw, 1.75rem)", lineHeight: 1.3, maxWidth: "40rem" }}>
            Cada día se mueven millones sin contexto. Una dirección es solo un hash hasta que
            alguien la investiga — y casi nadie tiene tiempo de hacerlo.
          </p>
        </Reveal>

        <Reveal label="Qué obtienes">
          <h2 className="eyebrow">Qué obtienes</h2>
          <ul className="bento">
            <li className="bento-cell bento-live">
              <strong>Vigilancia autónoma</strong>
              <p>Cada transacción de los últimos bloques, puntuada sola. Alertas sin pedir nada.</p>
              <p style={{ marginBlockStart: "0.75rem" }}>
                <Link href="/watch">Abrir vigilancia →</Link>
              </p>
            </li>
            <li className="bento-cell">
              <strong>Verificar antes de enviar</strong>
              <p>Mezcladores o bots visibles en segundos.</p>
            </li>
            <li className="bento-cell">
              <strong>Auditar contratos</strong>
              <p>Permisos peligrosos antes de firmar.</p>
            </li>
            <li className="bento-cell">
              <strong>Casos documentados</strong>
              <p>Reporte .md con rutas y explicación.</p>
            </li>
            <li className="bento-cell">
              <strong>Multi-red</strong>
              <p>Ethereum y Base, mismo motor.</p>
            </li>
          </ul>
        </Reveal>

        <Reveal label="Preguntas">
          <h2 className="eyebrow">Preguntas</h2>
          <div className="faq">
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
          </div>
        </Reveal>

        <Reveal label="Llamado final" className="reveal final-cta">
          <h2>
            Pega una dirección.
            <br />
            Entiende el riesgo.
          </h2>
          <Link href="/wallet" className="btn">
            Analizar una wallet
          </Link>
        </Reveal>
      </div>
    </main>
  );
}
