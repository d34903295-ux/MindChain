import type { Metadata } from "next";
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
          <div className="container">
            ChainMind — análisis heurístico automatizado. Verificar on-chain antes de actuar.
          </div>
        </footer>
      </body>
    </html>
  );
}
