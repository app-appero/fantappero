import { expect, test } from "@playwright/test";
import { waitForVerificationLink } from "../helpers/mailpit";
import { runSeedStage } from "../helpers/seed";

/**
 * EP12-01 — copre i 3 stati UI mancanti dei "Test minimi richiesti" (vuoto,
 * errore, permessi insufficienti), complementari al flusso positivo coperto
 * da `registration-to-league.spec.ts`. Gira contro lo stesso stack Docker
 * Compose reale (nessun mock). Dettagli in
 * docs/operations/beta_readiness/ep12-01_suite_e2e.md ("Stato implementazione").
 */

function uniqueEmail(prefix: string): string {
  return `${prefix}.${Date.now()}.${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function registerVerifyLogin(
  page: import("@playwright/test").Page,
  { displayName, email, password }: { displayName: string; email: string; password: string },
) {
  await page.goto("/accedi/registrati");
  await page.getByLabel("Nome visualizzato").fill(displayName);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Conferma password").fill(password);
  await page.getByRole("button", { name: "Registrati" }).click();
  await expect(page.getByTestId("auth-register-success")).toBeVisible();

  const verificationLink = await waitForVerificationLink(email);
  await page.goto(verificationLink);
  await expect(page.getByTestId("auth-verify-success")).toBeVisible();

  await login(page, { email, password });
}

async function login(
  page: import("@playwright/test").Page,
  { email, password }: { email: string; password: string },
) {
  await page.goto("/accedi");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Accedi" }).click();
  await expect(page).toHaveURL(/\/leghe/);
}

async function createLeague(page: import("@playwright/test").Page, leagueName: string) {
  await page.goto("/leghe/crea");
  await expect(page.getByTestId("create-league-form")).toBeVisible();
  await page.getByLabel("Nome lega").fill(leagueName);
  await page.getByTestId("create-league-select-all").click();
  await page.getByTestId("create-league-submit").click();

  const success = page.getByTestId("create-league-success");
  await expect(success).toBeVisible();
  await expect(success).toContainText(leagueName);
}

test("un utente crea una lega senza rosa e vede lo stato vuoto in formazione", async ({ page }) => {
  test.setTimeout(60_000);
  const email = uniqueEmail("e2e.state-empty");
  const password = "Password123!";
  const leagueName = `Lega E2E Vuota ${Date.now()}`;

  await test.step("registrazione, verifica, login, creazione lega", async () => {
    await registerVerifyLogin(page, { displayName: "Tester E2E Vuoto", email, password });
    await createLeague(page, leagueName);
  });

  await test.step("formazione: nessun turno disponibile (nessuna rosa/asta seedata)", async () => {
    await page.goto("/formazione");
    await expect(page.getByTestId("formation-empty")).toBeVisible();
  });
});

test("un utente prova a salvare una formazione incompleta e vede l'errore di validazione", async ({
  page,
}) => {
  test.setTimeout(120_000);
  const email = uniqueEmail("e2e.state-error");
  const password = "Password123!";
  const leagueName = `Lega E2E Errore ${Date.now()}`;

  await test.step("registrazione, verifica, login, creazione lega", async () => {
    await registerVerifyLogin(page, { displayName: "Tester E2E Errore", email, password });
    await createLeague(page, leagueName);
  });

  await test.step("seed rosa + turno (bypass asta reale — EP12-01 decisione rosa)", async () => {
    await runSeedStage("roster", { leagueName, ownerEmail: email });
  });

  await test.step("formazione: salvataggio con titolari incompleti mostra l'errore di validazione", async () => {
    await page.goto("/formazione");
    await expect(page.getByTestId("formation-round")).toBeVisible();

    // Riempie solo 10 degli 11 slot titolari (lascia vuoto l'ultimo): la
    // formazione è client-side invalida (starter_count_invalid /
    // missing_athlete) e il salvataggio deve essere rifiutato prima di
    // raggiungere il backend.
    for (let index = 0; index < 10; index += 1) {
      const trigger = page.getByTestId(`formation-starter-${index}`);
      await trigger.click();
      const options = page.getByTestId(`formation-starter-${index}-options`);
      await expect(options).toBeVisible();
      await options.locator('button[role="option"]').first().click();
    }

    await page.getByTestId("formation-save").click();
    await expect(page.getByTestId("formation-action-error")).toBeVisible();
    await expect(page.getByTestId("formation-success")).toHaveCount(0);
  });
});

test("un fantallenatore non amministratore tenta un'azione riservata e vede i permessi insufficienti", async ({
  browser,
}) => {
  test.setTimeout(150_000);
  const ownerEmail = uniqueEmail("e2e.state-forbidden-owner");
  const memberEmail = uniqueEmail("e2e.state-forbidden-member");
  const password = "Password123!";
  const leagueName = `Lega E2E Permessi ${Date.now()}`;
  const memberDisplayName = `Tester E2E Membro ${Date.now()}`;

  // Due browser context distinti (owner e membro) invece di login/logout
  // ripetuti sulla stessa pagina: simula due utenti/dispositivi reali e
  // dimezza il numero di login, che è soggetto al rate limit reale
  // dell'endpoint (5/minuto per IP — vedi backend/src/auth/service.py).
  const ownerContext = await browser.newContext();
  const memberContext = await browser.newContext();
  const ownerPage = await ownerContext.newPage();
  const memberPage = await memberContext.newPage();

  try {
    await test.step("owner: registrazione, verifica, login, creazione lega", async () => {
      await registerVerifyLogin(ownerPage, {
        displayName: "Tester E2E Owner",
        email: ownerEmail,
        password,
      });
      await createLeague(ownerPage, leagueName);
    });

    await test.step("membro: registrazione, verifica, login, disponibilità agli inviti", async () => {
      await registerVerifyLogin(memberPage, {
        displayName: memberDisplayName,
        email: memberEmail,
        password,
      });
      await memberPage.goto("/profilo");
      await expect(memberPage.getByTestId("profile-form")).toBeVisible();
      // Checkbox controllata in modo asincrono (l'update si riflette solo
      // dopo la risposta API): usa click() + expect a poll, non check()
      // (che richiede lo stato "checked" subito dopo l'evento).
      await memberPage.getByTestId("profile-invite-availability").click();
      await expect(memberPage.getByTestId("profile-invite-availability")).toBeChecked();
      await expect(memberPage.getByTestId("profile-success")).toBeVisible();
    });

    await test.step("owner: invita il membro nella lega dalla directory fantallenatori", async () => {
      await ownerPage.goto("/fantallenatori");
      const filtered = ownerPage.waitForResponse(
        (response) =>
          response.url().includes("/amministrazione/fantallenatori") &&
          response.url().includes("search=") &&
          response.status() === 200,
      );
      await ownerPage.getByLabel("Cerca per nome").fill(memberDisplayName);
      await filtered;
      const list = ownerPage.getByTestId("manager-directory-list");
      await expect(list.getByRole("button", { name: "Invita" })).toHaveCount(1);
      await list.getByRole("button", { name: "Invita" }).click();
      await expect(ownerPage.getByTestId("manager-directory-success")).toBeVisible();
    });

    await test.step("membro: accetta l'invito nominativo", async () => {
      await memberPage.goto("/inviti");
      await memberPage.getByRole("button", { name: "Accetta" }).click();
      await expect(memberPage.getByTestId("received-invites-success")).toBeVisible();
    });

    await test.step("membro: tenta l'amministrazione della lega e vede i permessi insufficienti", async () => {
      await memberPage.goto("/lega/amministrazione");
      await expect(memberPage.getByTestId("route-forbidden")).toBeVisible();
    });
  } finally {
    await ownerContext.close();
    await memberContext.close();
  }
});
