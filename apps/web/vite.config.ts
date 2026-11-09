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

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    strictPort: true,
    host: true,
    // ".fantappero.it" (prefisso punto) copre ogni sottodominio presente e futuro
    // (dev., pilota., ...) senza dover toccare questo file a ogni nuovo ambiente.
    allowedHosts: [
      "fantappero-web-dev.up.railway.app",
      "fantappero-web-pilot.up.railway.app",
      ".fantappero.it",
    ],
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
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setupActEnvironment.ts"],
  },
});
