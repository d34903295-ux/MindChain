import type { Metadata } from "next";
import Link from "next/link";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { SiteHeader } from "../components/ui";

const sans = Inter({ subsets: ["latin"], variable: "--font-sans", display: "swap" });
const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
  weight: ["400", "600"],
});

export const metadata: Metadata = {
  title: "ChainMind — Inteligencia blockchain",
  description: "Agentes de IA que vigilan wallets, contratos y transacciones en Ethereum y Base.",
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#0a0a0b" },
    { media: "(prefers-color-scheme: light)", color: "#fafaf7" },
  ],
  icons: { icon: "/icon.svg" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={`${sans.variable} ${mono.variable}`}>
      <body>
        <a href="#contenido" className="skip-link">
          Saltar al contenido
        </a>
        <SiteHeader />
        {children}
        <footer className="site-footer">
          <div className="container footer-grid">
            <div>
              <h2>ChainMind</h2>
              <p style={{ margin: "0.5rem 0 0" }}>
                Análisis heurístico automatizado. Verificar on-chain antes de actuar.
              </p>
            </div>
            <nav aria-label="Producto">
              <h2>Producto</h2>
              <ul>
                <li><Link href="/wallet">Wallet</Link></li>
                <li><Link href="/contract">Contrato</Link></li>
                <li><Link href="/watch">Vigilancia</Link></li>
              </ul>
            </nav>
            <nav aria-label="Recursos">
              <h2>Recursos</h2>
              <ul>
                <li><a href="http://localhost:8000/docs" target="_blank" rel="noreferrer">API</a></li>
                <li><a href="https://etherscan.io" target="_blank" rel="noreferrer">Etherscan</a></li>
                <li><a href="https://basescan.org" target="_blank" rel="noreferrer">Basescan</a></li>
              </ul>
            </nav>
          </div>
        </footer>
      </body>
    </html>
  );
}
