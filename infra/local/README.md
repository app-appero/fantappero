# infra/local

Configurazione Docker per lo sviluppo locale (EP01-02).

| File | Ruolo |
| --- | --- |
| `Dockerfile` | Immagine locale condivisa API/worker con quality gate backend |
| `Dockerfile.web` | Dev server Vite e quality gate workspace web/mobile |
| `.env.example` | Default locali (placeholder, non segreti di produzione) |
| `.env` | Override opzionale (gitignored) |

Documentazione operativa: [`docs/development/local_environment.md`](../../docs/development/local_environment.md).

Compose root: [`compose.yaml`](../../compose.yaml).

I test d'integrazione usano il servizio Compose opzionale `postgres-test` e il database
`fantappero_test`; le fixture rifiutano il database di sviluppo.
