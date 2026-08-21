# infra

Docker, ambienti, pipeline CI/CD e configurazione di deploy.

## Locale (EP01-02)

| Percorso | Ruolo |
| --- | --- |
| [`../compose.yaml`](../compose.yaml) | Stack Compose (essenziali + profile `tools`) |
| [`local/`](local/) | Dockerfile API/worker e env di esempio |
| [`scripts/`](scripts/) | `dev_up` / `dev_down` / `dev_logs` / `dev_reset` / `dev_healthcheck` / `smoke_local_stack` |
| [`../docs/development/local_environment.md`](../docs/development/local_environment.md) | Porte, comandi, troubleshooting |
| [`../docs/operations/backup_disaster_recovery.md`](../docs/operations/backup_disaster_recovery.md) | Backup PostgreSQL/avatar, restore isolato, RPO/RTO e drill EP12-05 |

```bash
make up && make health
# reset distruttivo volumi: make reset-local CONFIRM=yes
# backup manuale / drill restore isolato: make backup / make dr-restore-test
```

## Confini

- Segreti solo in secret manager / env protetti, mai in immagini pubbliche.
- Orchestrazione di `backend`, dipendenze (Postgres, Redis) e job.
- Default locali in `infra/local/.env.example` sono placeholder, non credenziali di produzione.

## CI (EP01-03)

| Percorso | Ruolo |
| --- | --- |
| [`../.github/workflows/ci.yml`](../.github/workflows/ci.yml) | Lint, format, typecheck, unit test, build, migrations |
| [`scripts/check_migrations.py`](scripts/check_migrations.py) | Controllo coerenza migrazioni (informativo fino a EP01-06) |
| [`../docs/development/quality_gates.md`](../docs/development/quality_gates.md) | Job obbligatori/informativi, comandi locali, cache |

```bash
make quality   # parità locale dei gate obbligatori + check migrazioni
```

Nessun secret di produzione richiesto dalla pipeline.

## Stato

Ambiente locale riproducibile (EP01-02). Quality gates CI (EP01-03). Deploy/CD oltre la CI resta fuori scope.
