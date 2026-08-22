/**
 * Runs `devtools.seed_e2e_scenario` inside the `api` container via
 * `docker compose run` (see compose.yaml) — the two states it reaches
 * (validated rosters, computed/homologated round result) are not reachable
 * from the UI at all in this release; see the "Stato implementazione"
 * section of `docs/operations/beta_readiness/ep12-01_suite_e2e.md` for why.
 */

import { exec } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { promisify } from "node:util";

const execAsync = promisify(exec);
const repoRoot = path.resolve(fileURLToPath(new URL("../../..", import.meta.url)));

function shellQuote(value: string): string {
  return `"${value.replace(/(["\\$`])/g, "\\$1")}"`;
}

export type SeedStage = "roster" | "results";

export async function runSeedStage(
  stage: SeedStage,
  opts: { leagueName: string; ownerEmail: string },
): Promise<void> {
  const command = [
    "docker",
    "compose",
    "run",
    "--rm",
    "api",
    "python",
    "-m",
    "devtools.seed_e2e_scenario",
    "--stage",
    stage,
    "--league-name",
    shellQuote(opts.leagueName),
    "--owner-email",
    shellQuote(opts.ownerEmail),
  ].join(" ");

  try {
    await execAsync(command, { cwd: repoRoot, timeout: 180_000 });
  } catch (error) {
    const err = error as { stdout?: string; stderr?: string; message: string };
    throw new Error(
      `seed_e2e_scenario --stage ${stage} failed: ${err.stderr || err.stdout || err.message}`,
    );
  }
}
