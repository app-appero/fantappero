# infra/local

Configurazione Docker per lo sviluppo locale (EP01-02, EP02-01 web).

| File | Ruolo |
| --- | --- |
| `Dockerfile` | Immagine condivisa API FastAPI + worker Celery |
| `Dockerfile.web` | Dev server Vite (`apps/web`) |
| `.env.example` | Default locali (placeholder, non segreti di produzione) |
| `.env` | Override opzionale (gitignored) |

Documentazione operativa: [`docs/development/local_environment.md`](../../docs/development/local_environment.md).

Compose root: [`compose.yaml`](../../compose.yaml).

Mobile (Expo) **non** è containerizzato — avvio su host: `pnpm dev:mobile`.
