/**
 * Base de la API de ChainMind para el navegador.
 *
 * Antes estaba `http://localhost:8000` escrito en 17 sitios, lo que hacía
 * imposible desplegar la web en otro sitio que no fuera esta máquina: en
 * Netlify (o en cualquier hosting) el navegador pide a su propio localhost y
 * no llega a nada.
 *
 * `NEXT_PUBLIC_*` lo sustituye Next.js en tiempo de build, así que el valor
 * queda dentro del bundle y funciona en cliente sin configurar nada más.
 * Defecto: `http://localhost:8000`, que es lo correcto para el uso local.
 *
 * En Netlify: Site settings → Environment variables → NEXT_PUBLIC_API_URL con
 * la URL pública del backend. Sin eso, la web carga pero no habla con la API.
 */
export const API_BASE =
  (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");

/** Une la base con una ruta sin duplicar ni perder la barra. */
export function api(ruta: string): string {
  return `${API_BASE}${ruta.startsWith("/") ? ruta : `/${ruta}`}`;
}
