import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
// Gli stessi testi che la schermata prende da `@fantappero/contracts` (qui dal sorgente).
import { appVersionSaveConfirmation } from "../../../../packages/contracts/src/appVersion.ts";
import { confirmAppVersionSave, type ConfirmAlertButton } from "./saveConfirm.ts";

const UPDATE = {
  latestVersionName: "1.4.0",
  latestVersionCode: 5,
  downloadUrl: "https://drive.google.com/drive/folders/fantappero-1-4",
  message: null,
};
const ANNOUNCED_13 = { ...UPDATE, latestVersionName: "1.3.0", latestVersionCode: 4 };

function fakeAlert() {
  const shown: { title: string; message: string; buttons: ConfirmAlertButton[] }[] = [];
  return {
    shown,
    alert: (title: string, message: string, buttons: ConfirmAlertButton[]) => {
      shown.push({ title, message, buttons });
    },
  };
}

describe("«Sei sicuro?» prima di salvare la versione dell'app (Rosario 23/11)", () => {
  it("chiede «Annunciare la versione 1.4.0 (versionCode 5)?» con «Annulla» e «Annuncia»", () => {
    const { shown, alert } = fakeAlert();
    let saved = 0;
    confirmAppVersionSave(alert, appVersionSaveConfirmation(UPDATE, ANNOUNCED_13), () => {
      saved += 1;
    });

    assert.equal(saved, 0, "non salva prima della conferma");
    const [only] = shown;
    assert.ok(only);
    assert.equal(only.title, "Annunciare la versione 1.4.0 (versionCode 5)?");
    assert.equal(
      only.message,
      "Tutti gli utenti che usano l'app Android (o il sito da un telefono Android) e non hanno ancora questa versione riceveranno una notifica; nell'app vedranno anche l'avviso di aggiornamento.",
    );
    assert.deepEqual(
      only.buttons.map((button) => [button.text, button.style ?? "default"]),
      [
        ["Annulla", "cancel"],
        ["Annuncia", "default"],
      ],
    );
    // «Annulla» non salva; «Annuncia» salva una volta.
    only.buttons[0]?.onPress?.();
    assert.equal(saved, 0);
    only.buttons[1]?.onPress?.();
    assert.equal(saved, 1);
  });

  it("stesso versionCode già annunciato: «Salva» e la notifica non riparte", () => {
    const { shown, alert } = fakeAlert();
    confirmAppVersionSave(alert, appVersionSaveConfirmation(UPDATE, UPDATE), () => {});
    assert.equal(shown[0]?.title, "Salvare le modifiche alla versione 1.4.0 (versionCode 5)?");
    assert.match(shown[0]?.message ?? "", /la notifica non parte di nuovo/);
    assert.deepEqual(
      shown[0]?.buttons.map((button) => button.text),
      ["Annulla", "Salva"],
    );
  });

  it("la schermata «Versione app» salva solo dalla conferma", () => {
    const source = readFileSync(
      new URL("../screens/admin/AdminAppVersionScreen.tsx", import.meta.url),
      "utf8",
    );
    assert.match(source, /confirmAppVersionSave\(\s*Alert\.alert,/);
    assert.match(source, /appVersionSaveConfirmation\(update, current\?\.android \?\? null\)/);
    // Il tasto «Salva» chiede conferma, non salva direttamente.
    assert.match(source, /onPress=\{requestSave\}/);
    assert.doesNotMatch(source, /onPress=\{\(\) => void save\(\)\}/);
  });
});
