import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { afterEach, describe, it } from "node:test";
import {
  THEME_SCROLL_TTL_MS,
  clearThemeScroll,
  pendingThemeScroll,
  rememberScrollBeforeThemeChange,
  themeScrollTarget,
} from "./themeScrollRestore.ts";

describe("Profilo: dopo il cambio tema la pagina resta dov'era (QA 22/11)", () => {
  afterEach(() => clearThemeScroll());

  it("il punto segnato prima del cambio si ritrova dopo il rimontaggio", () => {
    rememberScrollBeforeThemeChange(840, 1_000);
    assert.equal(pendingThemeScroll(1_500), 840);
    // Leggerlo non lo consuma: lo toglie chi lo usa.
    assert.equal(pendingThemeScroll(1_600), 840);
    clearThemeScroll();
    assert.equal(pendingThemeScroll(1_700), null);
  });

  it("un punto vecchio (tema cambiato senza rimontare la pagina) non vale più", () => {
    rememberScrollBeforeThemeChange(840, 1_000);
    assert.equal(pendingThemeScroll(1_000 + THEME_SCROLL_TTL_MS + 1), null);
  });

  it("senza cambio tema non c'è nulla da ritrovare, e lo scorrimento non è mai negativo", () => {
    assert.equal(pendingThemeScroll(), null);
    rememberScrollBeforeThemeChange(-30, 1_000);
    assert.equal(pendingThemeScroll(1_001), 0);
  });

  it("si torna al punto di prima, ma non oltre la fine della pagina", () => {
    assert.equal(themeScrollTarget(840, 2_400, 700), 840);
    assert.equal(themeScrollTarget(2_000, 2_400, 700), 1_700);
    assert.equal(themeScrollTarget(300, 500, 700), 0);
  });

  it("il Profilo segna il punto prima di cambiare tema e ci torna a pagina completa", () => {
    const source = readFileSync(new URL("../screens/ProfileScreen.tsx", import.meta.url), "utf8");
    assert.match(source, /<ThemePreferenceSection onBeforeChange=\{rememberScroll\} \/>/);
    assert.match(source, /if \(option\.value !== preference\) \{\n\s*onBeforeChange\?\.\(\);\n\s*\}\n\s*setPreference\(option\.value\);/);
    assert.match(source, /restoreYRef\.current = pendingThemeScroll\(\);/);
    assert.match(source, /onContentSizeChange=\{restoreScroll\}/);
    assert.match(source, /themeScrollTarget\(y, contentHeight, viewportHeightRef\.current\)/);
    const page = readFileSync(new URL("../layout/PageContainer.tsx", import.meta.url), "utf8");
    assert.match(page, /ref=\{scrollRef\}/);
    assert.match(page, /onContentSizeChange=\{onContentSizeChange\}/);
  });
});
