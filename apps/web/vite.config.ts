import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Niente "/admin": è anche il prefisso delle pagine SPA del pannello operatore
// (/admin, /admin/utenti, /admin/leghe, ...). Il client chiama comunque l'API
// con l'URL assoluto di VITE_API_BASE_URL, non con path relativi — questo
// proxy serve solo da comodità di dev per gli altri prefissi; su "/admin"
// intercettava anche i reload diretti delle pagine SPA, mandandole in 500.
const API_PROXY_PREFIXES = [
  "/auth",
  "/profile",
  "/leagues",
  "/notifications",
  "/billing",
  "/assistente",
  "/fantasy-lineups",
  "/fantasy-scoring",
  "/fantasy-ratings",
  "/sports-data",
  "/media",
  "/health",
  "/live",
  "/ready",
  "/metrics",
];

const apiProxyTarget = process.env.VITE_API_PROXY_TARGET?.trim() || "http://127.0.0.1:8001";

// ".fantappero.it" (prefisso punto) copre ogni sottodominio presente e futuro
// (dev., pilota., ...) senza dover toccare questo file a ogni nuovo ambiente.
const ALLOWED_HOSTS = [
  "fantappero-web-dev.up.railway.app",
  "fantappero-web-pilot.up.railway.app",
  ".fantappero.it",
];

// Railway instrada il traffico verso questo servizio su una porta fissa
// (configurata nel pannello Networking, non tramite $PORT dinamico): va
// condivisa identica da dev server e preview, altrimenti il processo parte
// ma su una porta che da fuori nessuno raggiunge (502).
const PORT = 5174;

export default defineConfig({
  plugins: [react()],
  server: {
    port: PORT,
    strictPort: true,
    host: true,
    allowedHosts: ALLOWED_HOSTS,
    proxy: Object.fromEntries(
      API_PROXY_PREFIXES.map((prefix) => [
        prefix,
        { target: apiProxyTarget, changeOrigin: true },
      ]),
    ),
    watch: {
      usePolling: true,
      interval: 300,
    },
  },
  // Serve la build di produzione (`pnpm start`, dopo `pnpm build`): a differenza del
  // dev server sopra, qui non gira codice sorgente non compilato né il WebSocket HMR —
  // è quello che Railway deve eseguire per dev/pilota invece del dev server grezzo
  // (vedi docs/operations/beta_readiness/ep12-04_security_review.md, finding nuovo
  // "dev server Vite esposto in produzione").
  preview: {
    host: true,
    port: PORT,
    strictPort: true,
    allowedHosts: ALLOWED_HOSTS,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setupActEnvironment.ts"],
  },
});
