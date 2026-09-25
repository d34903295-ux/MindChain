import Link from "next/link";
import { GlyphField } from "../components/GlyphField";
import { OpsCenter } from "../components/OpsCenter";
import { Magnetic, SplitLines, Spotlight, Stagger, Tilt } from "../components/motion";
import { Reveal } from "../components/Reveal";

export default function Landing() {
  return (
    <main id="contenido">
      <div className="landing-wide">
        <div className="hero-grid hero-stage" style={{ gridTemplateColumns: "1fr", paddingBlockEnd: "0.5rem" }}>
          <GlyphField />
          <section aria-labelledby="hero" style={{ maxWidth: "56rem" }}>
            <p className="eyebrow hero-enter">Ethereum · Base · 7 agentes de IA</p>
            <h1 id="hero" className="display-xl" style={{ marginBlock: "0.75rem 1rem" }}>
              <SplitLines
                lines={[
                  <>Un centro de inteligencia</>,
                  <>
                    blockchain que <span className="accent">nunca duerme.</span>
                  </>,
                ]}
              />
            </h1>
            <p className="lede hero-enter hero-enter-2">
              Siete agentes especializados: perfilan wallets, auditan contratos, rastrean
              transacciones, puntúan riesgo y redactan la explicación. Tú eliges la red; el
              centinela sigue vigilando cuando cierras el panel.
            </p>
            <div className="cta-row hero-enter hero-enter-3">
              <Magnetic>
                <Link href="/wallet" className="btn">
                  Analizar una wallet
                </Link>
              </Magnetic>
              <Link href="/watch" className="quiet-link">
                Ver vigilancia en vivo →
              </Link>
            </div>
            <dl className="stat-grid hero-enter hero-enter-4" aria-label="Datos del sistema" style={{ marginBlockStart: 0 }}>
              <div className="stat">
                <dt>Redes</dt>
                <dd>2</dd>
              </div>
              <div className="stat">
                <dt>Agentes</dt>
                <dd>7</dd>
              </div>
              <div className="stat">
                <dt>Análisis</dt>
                <dd className="mono">~7 s</dd>
              </div>
              <div className="stat">
                <dt>Tests</dt>
                <dd className="mono">243</dd>
              </div>
            </dl>
          </section>
        </div>
      </div>

      <section className="ops-host" aria-labelledby="ops-title" style={{ paddingBlock: "1.5rem 1rem" }}>
        <h2 id="ops-title" className="eyebrow is-centered">
          La sala de operaciones
        </h2>
        <Tilt max={2} className="ops-tilt">
          <OpsCenter />
        </Tilt>
      </section>

      <div className="landing-wide">
        <Reveal label="Prueba operacional" className="reveal proof-band">
          <dl className="proof-grid">
            <div>
              <dt>Agentes operando</dt>
              <dd>7</dd>
            </div>
            <div>
              <dt>Redes vigiladas</dt>
              <dd>2</dd>
            </div>
            <div>
              <dt>Tests automatizados</dt>
              <dd>243</dd>
            </div>
            <div>
              <dt>Análisis con IA local</dt>
              <dd>~7 s</dd>
            </div>
          </dl>
        </Reveal>

        <Reveal label="El problema">
          <h2 className="eyebrow">El problema</h2>
          <p className="statement">
            Cada día se mueven millones sin contexto. Una dirección es solo un hash hasta que
            alguien la investiga — y casi nadie tiene tiempo de hacerlo.
          </p>
        </Reveal>

        <Reveal label="El pipeline de agentes">
          <h2 className="eyebrow">Cómo colaboran los agentes</h2>
          <p className="section-lede">
            Cada transacción recorre la misma cadena de especialistas. Ninguno improvisa: cada uno
            entrega un artefacto verificable al siguiente.
          </p>
          <Stagger as="ol" className="pipeline">
            <li>
              <span className="pipeline-step">01</span>
              <div>
                <strong>Monitoring Agent</strong>
                <p>Lee bloques nuevos y detecta desviaciones frente a la mediana de la red.</p>
              </div>
            </li>
            <li>
              <span className="pipeline-step">02</span>
              <div>
                <strong>Transaction Agent</strong>
                <p>Normaliza valor, gas, origen y destino; clasifica el tipo de movimiento.</p>
              </div>
            </li>
            <li>
              <span className="pipeline-step">03</span>
              <div>
                <strong>Wallet Agent</strong>
                <p>Perfila antigüedad, contrapartes y patrón horario: humano o bot.</p>
              </div>
            </li>
            <li>
              <span className="pipeline-step">04</span>
              <div>
                <strong>Contract Agent</strong>
                <p>Descompila bytecode y busca permisos peligrosos en contratos verificados.</p>
              </div>
            </li>
            <li>
              <span className="pipeline-step">05</span>
              <div>
                <strong>Risk Agent</strong>
                <p>Puntúa 0–100 con heurísticas: mezcladores, concentración, anomalías.</p>
              </div>
            </li>
            <li>
              <span className="pipeline-step">06</span>
              <div>
                <strong>Research Agent</strong>
                <p>Contrasta con exploradores y fuentes públicas antes de afirmar.</p>
              </div>
            </li>
            <li>
              <span className="pipeline-step">07</span>
              <div>
                <strong>Explanation Agent</strong>
                <p>Único agente con LLM: traduce el score a lenguaje humano, con Claude.</p>
              </div>
            </li>
          </Stagger>
        </Reveal>

        <Reveal label="Qué obtienes">
          <h2 className="eyebrow">Capacidades</h2>
          <Stagger as="ul" className="bento">
            <Spotlight className="bento-cell-wrap">
              <li className="bento-cell bento-live">
                <span className="bento-kicker">24/7</span>
                <strong>Vigilancia autónoma</strong>
                <p>Cada transacción de los últimos bloques, puntuada sola. Alertas sin pedir nada.</p>
                <p className="bento-link">
                  <Link href="/watch">Abrir vigilancia →</Link>
                </p>
              </li>
            </Spotlight>
            <Spotlight className="bento-cell-wrap">
              <li className="bento-cell">
                <span className="bento-kicker">Wallets</span>
                <strong>Verificar antes de enviar</strong>
                <p>Mezcladores, bots o concentración de fondos visibles en segundos.</p>
              </li>
            </Spotlight>
            <Spotlight className="bento-cell-wrap">
              <li className="bento-cell">
                <span className="bento-kicker">Contratos</span>
                <strong>Auditar bytecode</strong>
                <p>DELEGATECALL, SELFDESTRUCT, mint privilegiado y pausa centralizada.</p>
              </li>
            </Spotlight>
            <Spotlight className="bento-cell-wrap">
              <li className="bento-cell">
                <span className="bento-kicker">Casos</span>
                <strong>Reporte descargable</strong>
                <p>Markdown con perfil, riesgo, rutas de fondos y explicación.</p>
              </li>
            </Spotlight>
            <Spotlight className="bento-cell-wrap">
              <li className="bento-cell">
                <span className="bento-kicker">Multi-red</span>
                <strong>Ethereum y Base</strong>
                <p>Mismo motor de agentes, sin código duplicado por cadena.</p>
              </li>
            </Spotlight>
          </Stagger>
        </Reveal>

        <Reveal label="Cómo se usa" className="reveal steps-section">
          <h2 className="eyebrow">Cómo se usa</h2>
          <Stagger as="ol" className="steps">
            <li>
              <div>
                <strong>Elige red y objetivo</strong>
                <p>
                  En <Link href="/wallet">Wallet</Link> pega una dirección 0x. En{" "}
                  <Link href="/watch">Vigilancia</Link> basta elegir la red.
                </p>
              </div>
            </li>
            <li>
              <div>
                <strong>Lee el score</strong>
                <p>0–29 bajo · 30–69 medio · 70–100 alto. Cada factor, explicado en claro.</p>
              </div>
            </li>
            <li>
              <div>
                <strong>Profundiza o descarga</strong>
                <p>
                  Traza fondos, audita el <Link href="/contract">contrato</Link> o baja el .md.
                </p>
              </div>
            </li>
          </Stagger>
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
              <summary>¿Cuánto cuesta operarlo?</summary>
              <p>Nada hasta nuevo aviso: corre en tu máquina con fuentes públicas. El LLM es opcional.</p>
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
          <h2 className="display-l">
            <SplitLines lines={[<>Pega una dirección.</>, <>Entiende el riesgo.</>]} />
          </h2>
          <Magnetic>
            <Link href="/wallet" className="btn">
              Analizar una wallet
            </Link>
          </Magnetic>
        </Reveal>
      </div>
    </main>
  );
}
