import type { IncomingMessage, ServerResponse } from "node:http";
import { defineConfig } from "vitest/config";
import type { Plugin } from "vite";
import react from "@vitejs/plugin-react";
import { ASSET_LINKS_PATH, buildAssetLinks } from "./src/config/assetLinks";

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

// App Link Android: /.well-known/assetlinks.json esiste solo dove il servizio web ha
// ANDROID_APP_LINK_SHA256 (vedi src/config/assetLinks.ts). Vale per dev server e preview.
function androidAssetLinks(): Plugin {
  const serve = (req: IncomingMessage, res: ServerResponse, next: () => void) => {
    if (req.url?.split("?")[0] !== ASSET_LINKS_PATH) {
      next();
      return;
    }
    const body = buildAssetLinks(process.env.ANDROID_APP_LINK_SHA256);
    res.statusCode = body ? 200 : 404;
    res.setHeader("content-type", "application/json");
    res.end(body ?? "[]");
  };
  return {
    name: "fantappero-android-asset-links",
    configureServer(server) {
      server.middlewares.use(serve);
    },
    configurePreviewServer(server) {
      server.middlewares.use(serve);
    },
  };
}

export default defineConfig({
  plugins: [react(), androidAssetLinks()],
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
