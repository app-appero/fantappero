# infra/local

Configurazione Docker per lo sviluppo locale (EP01-02).

| File | Ruolo |
| --- | --- |
| `Dockerfile` | Immagine condivisa API FastAPI + worker Celery |
| `.env.example` | Default locali (placeholder, non segreti di produzione) |
| `.env` | Override opzionale (gitignored) |

Documentazione operativa: [`docs/development/local_environment.md`](../../docs/development/local_environment.md).

Compose root: [`compose.yaml`](../../compose.yaml).
