import { API_BASE } from "../lib/api";
import type { Metadata, Viewport } from "next";
import Link from "next/link";
import { Sora, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { SiteHeader } from "../components/ui";
import { ReadProgress } from "../components/motion";

const sans = Sora({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
  weight: ["300", "400", "500", "600", "700"],
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  metadataBase: new URL("http://localhost:3000"),
  title: {
    default: "ChainMind — Inteligencia blockchain operada por IA",
    template: "%s · ChainMind",
  },
  description:
    "Siete agentes de IA vigilan wallets, contratos y transacciones en Ethereum y Base. Perfil, score de riesgo y reporte con IA local o en la nube.",
  applicationName: "ChainMind",
  keywords: ["blockchain intelligence", "anomalías", "Ethereum", "Base", "agents IA", "on-chain"],
  openGraph: {
    type: "website",
    locale: "es_ES",
    title: "ChainMind — Inteligencia blockchain operada por IA",
    description:
      "Monitoring, Transaction, Wallet, Contract, Risk, Research y Explanation trabajando 24/7 sobre la cadena.",
    siteName: "ChainMind",
  },
  icons: { icon: "/icon.svg" },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#0b0d12" },
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
  ],
  width: "device-width",
  initialScale: 1,
  colorScheme: "light dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={`${sans.variable} ${mono.variable}`}>
      <body>
        <a href="#contenido" className="skip-link">
          Saltar al contenido
        </a>
        <ReadProgress />
        <SiteHeader />
        {children}
        <footer className="site-footer">
          <div className="container footer-grid">
            <div>
              <h2>ChainMind</h2>
              <p style={{ margin: "0.5rem 0 0", maxWidth: "34ch" }}>
                Inteligencia blockchain operada por agentes de IA. Verifica on-chain antes de actuar.
              </p>
              <p className="footer-status">
                <span className="footer-dot" aria-hidden="true" /> 7 agentes · 2 redes · operating 24/7
              </p>
            </div>
            <nav aria-label="Producto">
              <h2>Producto</h2>
              <ul>
                <li><Link href="/watch">Vigilancia</Link></li>
                <li><Link href="/wallet">Wallet</Link></li>
                <li><Link href="/contract">Contrato</Link></li>
              </ul>
            </nav>
            <nav aria-label="Recursos">
              <h2>Recursos</h2>
              <ul>
                <li><a href="${API_BASE}/docs" target="_blank" rel="noreferrer">API (OpenAPI)</a></li>
                <li><a href="https://etherscan.io" target="_blank" rel="noreferrer">Etherscan</a></li>
                <li><a href="https://basescan.org" target="_blank" rel="noreferrer">Basescan</a></li>
              </ul>
            </nav>
          </div>
          <div className="container footer-legal">
            <span>© {new Date().getFullYear()} ChainMind</span>
            <span>Análisis heurístico automatizado · no es asesoramiento financiero</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
