import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  DEFAULT_RESTORE_BEFORE,
  LISTONE_REFRESH_OPTIONS,
  LISTONE_REFRESH_ROLES_WARNING,
  formatRomeLocal,
  listoneRefreshStartLabel,
  listoneRefreshSummary,
  listoneRestoreConfirmText,
  listoneRestoreDoneMessage,
  listoneRestoreEmptyMessage,
  listoneRestoreSummary,
  listoneRoleChangesLabel,
  listoneRoleChangesSummary,
  listoneRolesAppliedMessage,
  romeLocalToIso,
} from "./listoneRoles.ts";

describe("«Aggiorna listone dal provider»: scelta e anteprima dei ruoli (sito dal 22/11, app 1.5)", () => {
  it("la scelta ha due opzioni: ruoli congelati (predefinita) o aggiornati dal fornitore", () => {
    assert.deepEqual(
      LISTONE_REFRESH_OPTIONS.map((option) => option.mode),
      ["keep_roles", "update_roles"],
    );
    assert.equal(
      LISTONE_REFRESH_OPTIONS[0]?.title,
      "Aggiungi i nuovi calciatori e aggiorna le squadre",
    );
    assert.equal(
      LISTONE_REFRESH_OPTIONS[0]?.hint,
      "I ruoli dei calciatori già nel listone restano come sono.",
    );
    assert.equal(LISTONE_REFRESH_OPTIONS[1]?.title, "Aggiorna anche i ruoli dal fornitore");
    assert.match(LISTONE_REFRESH_ROLES_WARNING, /possono andare fuori quota\.$/);
    assert.equal(listoneRefreshStartLabel("keep_roles"), "Aggiorna listone");
    assert.equal(listoneRefreshStartLabel("update_roles"), "Aggiorna e mostra i ruoli");
  });

  it("l'esito dice quanti ruoli sono rimasti com'erano", () => {
    assert.equal(
      listoneRefreshSummary("Listone aggiornato.", 3, 5, 0),
      "Listone aggiornato. Creati: 3, aggiornati: 5.",
    );
    assert.equal(
      listoneRefreshSummary("Listone aggiornato.", 3, 5, 2),
      "Listone aggiornato. Creati: 3, aggiornati: 5. Ruoli lasciati com'erano (il fornitore ne indica un altro): 2.",
    );
  });

  it("l'anteprima dei ruoli conta i calciatori e le rose fuori quota prima e dopo", () => {
    assert.equal(listoneRoleChangesLabel(1), "1 calciatore cambierebbe ruolo");
    assert.equal(listoneRoleChangesLabel(4), "4 calciatori cambierebbero ruolo");
    assert.equal(
      listoneRoleChangesSummary({ changes: 4, rostersOverQuotaNow: 1, rostersOverQuotaAfter: 3 }),
      "4 calciatori cambierebbero ruolo · Rose fuori quota con questi calciatori: ora 1, con i nuovi ruoli 3",
    );
    assert.equal(
      listoneRolesAppliedMessage({ applied: 4, rostersResynced: 2 }),
      "Ruoli aggiornati dal fornitore: 4. Rose ricalcolate: 2.",
    );
  });
});

describe("«Ripristina i ruoli cambiati da un aggiornamento» (sito, app 1.5)", () => {
  it("l'ora si legge sempre come ora di Roma, con la T o con lo spazio", () => {
    // 21/11/2026 è ora solare (UTC+1).
    assert.equal(DEFAULT_RESTORE_BEFORE, "2026-11-21T12:00");
    assert.equal(romeLocalToIso("2026-11-21T12:00"), "2026-11-21T11:00:00.000Z");
    assert.equal(romeLocalToIso("2026-11-21 12:00"), "2026-11-21T11:00:00.000Z");
    // Estate (UTC+2).
    assert.equal(romeLocalToIso("2026-07-01T12:00"), "2026-07-01T10:00:00.000Z");
    assert.equal(romeLocalToIso("non è una data"), null);
    assert.equal(formatRomeLocal("2026-11-21T12:00"), "21/11/2026 alle 12:00");
    assert.equal(formatRomeLocal("2026-11-21 09:05"), "21/11/2026 alle 09:05");
  });

  it("anteprima, conferma ed esito", () => {
    assert.equal(
      listoneRestoreSummary({
        toRestore: 2,
        notReconstructible: 1,
        rostersOverQuotaNow: 3,
        rostersOverQuotaAfter: 0,
      }),
      "Da ripristinare: 2 · Non ricostruibili: 1 · Rose fuori quota con questi calciatori: ora 3, dopo il ripristino 0",
    );
    assert.equal(
      listoneRestoreEmptyMessage("2026-11-21T12:00"),
      "Nessun ruolo cambiato dopo il 21/11/2026 alle 12:00.",
    );
    assert.match(
      listoneRestoreConfirmText(1, "2026-11-21T12:00"),
      /^Riporti 1 calciatore al ruolo che avevano prima del 21\/11\/2026 alle 12:00\./,
    );
    assert.match(listoneRestoreConfirmText(5, "2026-11-21T12:00"), /^Riporti 5 calciatori al ruolo/);
    assert.match(listoneRestoreConfirmText(5, "2026-11-21T12:00"), /Confermi\?$/);
    assert.equal(
      listoneRestoreDoneMessage({ restored: 5, rostersResynced: 2 }),
      "Ruoli ripristinati: 5. Rose ricalcolate: 2. Controlla le rose e la generazione del calendario.",
    );
  });
});
