# Apply Alembic migrations against the Compose Postgres (Windows-friendly).
# Uses the Docker network (hostname `postgres`) so host DATABASE_URL / port 5432 conflicts are avoided.
#
# Usage (from repo root or anywhere):
#   .\infra\scripts\migrate.ps1
#   .\infra\scripts\migrate.ps1 current
#   .\infra\scripts\migrate.ps1 "downgrade -1"

param(
    [Parameter(Position = 0)]
    [string]$AlembicArgs = "upgrade head"
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$EnvFile = if (Test-Path (Join-Path $RepoRoot "infra\local\.env")) {
    "infra/local/.env"
} else {
    "infra/local/.env.example"
}

$postgresRunning = docker ps --filter "name=fantappero-postgres" --filter "status=running" -q
if (-not $postgresRunning) {
    Write-Error @"
fantappero-postgres is not running.

Start the stack first:
  docker compose --env-file infra/local/.env.example up -d --build
"@
}

Push-Location $RepoRoot
try {
    Write-Host "Running alembic $AlembicArgs (env: $EnvFile) ..."
    docker compose --env-file $EnvFile run --rm --no-deps api python -m alembic $AlembicArgs.Split(" ")
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    Write-Host "Migrations applied."
} finally {
    Pop-Location
}
