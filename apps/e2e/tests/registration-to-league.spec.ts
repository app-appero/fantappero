import { expect, test } from "@playwright/test";
import { waitForVerificationLink } from "../helpers/mailpit";
import { runSeedStage } from "../helpers/seed";

/**
 * EP12-01 — copre il flusso critico Beta completo:
 * registrazione → lega → rosa → formazione → risultato → mercato.
 * Gira contro lo stack Docker Compose reale (web+api+postgres+redis+
 * mailpit), non contro mock — coerente con "ambiente pulito e dati fixture"
 * richiesto dai criteri di accettazione della card.
 *
 * Rosa e risultato turno non sono raggiungibili da UI in questa release
 * (asta reale fragile/costosa da guidare via Playwright; il calcolo dei
 * risultati richiede Permission.GLOBAL_OPERATE e il tab "Risultati" è un
 * placeholder statico) — vengono popolati dallo script di seed backend
 * `devtools.seed_e2e_scenario`, che chiama i servizi di dominio reali (mai
 * HTTP/UI). Formazione e mercato restano guidati da UI reale. Dettagli e
 * motivazione completa in docs/operations/beta_readiness/ep12-01_suite_e2e.md
 * ("Stato implementazione").
 */

function uniqueEmail(prefix: string): string {
  return `${prefix}.${Date.now()}.${Math.random().toString(36).slice(2, 8)}@example.com`;
}

test("un utente si registra, verifica l'email, accede, crea una lega, schiera la formazione e opera sul mercato", async ({
  page,
}) => {
  test.setTimeout(180_000);
  const email = uniqueEmail("e2e.critical-flow");
  const password = "Password123!";
  const leagueName = `Lega E2E ${Date.now()}`;

  await test.step("registrazione", async () => {
    await page.goto("/accedi/registrati");
    await page.getByLabel("Nome visualizzato").fill("Tester E2E");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByLabel("Conferma password").fill(password);
    await page.getByRole("button", { name: "Registrati" }).click();
    await expect(page.getByTestId("auth-register-success")).toBeVisible();
  });

  await test.step("verifica email via Mailpit", async () => {
    const verificationLink = await waitForVerificationLink(email);
    await page.goto(verificationLink);
    await expect(page.getByTestId("auth-verify-success")).toBeVisible();
  });

  await test.step("login", async () => {
    await page.goto("/accedi");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Accedi" }).click();
    await expect(page).toHaveURL(/\/leghe/);
  });

  await test.step("creazione lega privata", async () => {
    await page.goto("/leghe/crea");
    await expect(page.getByTestId("create-league-form")).toBeVisible();
    await page.getByLabel("Nome lega").fill(leagueName);
    await page.getByTestId("create-league-select-all").click();
    await page.getByTestId("create-league-submit").click();

    const success = page.getByTestId("create-league-success");
    await expect(success).toBeVisible();
    await expect(success).toContainText(leagueName);
  });

  await test.step("seed rosa + turno (bypass asta reale — EP12-01 decisione rosa)", async () => {
    await runSeedStage("roster", { leagueName, ownerEmail: email });
  });

  await test.step("formazione", async () => {
    await page.goto("/formazione");
    await expect(page.getByTestId("formation-round")).toBeVisible();

    // Il modulo di default (4-3-3, 1P-4D-3C-3A) è già selezionato: riempie
    // gli 11 slot titolari scegliendo la prima opzione disponibile per ogni
    // ruolo dalla rosa sintetica validata dal seed.
    for (let index = 0; index < 11; index += 1) {
      const trigger = page.getByTestId(`formation-starter-${index}`);
      await trigger.click();
      const options = page.getByTestId(`formation-starter-${index}-options`);
      await expect(options).toBeVisible();
      await options.locator('button[role="option"]').first().click();
    }

    await page.getByTestId("formation-save").click();
    await expect(page.getByTestId("formation-success")).toBeVisible();
  });

  await test.step("seed risultato turno (bypass calcolo voti/omologazione — EP12-01 decisione risultato)", async () => {
    await runSeedStage("results", { leagueName, ownerEmail: email });
  });

  await test.step("mercato: svincolo volontario", async () => {
    await page.goto("/mercato");
    await expect(page.getByTestId("market-release-section")).toBeVisible();

    await page.getByLabel("Giocatore da svincolare").selectOption({ index: 1 });
    await page.getByRole("button", { name: "Calcola rimborso" }).click();
    await expect(page.getByTestId("market-release-preview")).toBeVisible();

    await page.getByRole("button", { name: "Conferma svincolo" }).click();
    await expect(page.getByTestId("market-release-apply-success")).toBeVisible();
  });
});
