import assert from "node:assert/strict";
import { test } from "node:test";
import { clubAbbreviation, clubCrestSvg, clubCrestUrl, leagueBadgeSvg } from "./playerAvatar.ts";

test("sigle dei club noti e fallback", () => {
  assert.equal(clubAbbreviation("Inter"), "INT");
  assert.equal(clubAbbreviation("Paris Saint Germain"), "PSG");
  assert.equal(clubAbbreviation("Club Inventato"), "CLU");
  assert.equal(clubAbbreviation(null), "—");
});

test("lo stemma è un SVG stabile e il distintivo del campionato esiste per tutti e 5", () => {
  assert.equal(clubCrestSvg("Napoli"), clubCrestSvg("Napoli"));
  assert.ok(clubCrestUrl("Napoli").startsWith("data:image/svg+xml"));
  for (const name of ["Serie A", "Premier League", "LaLiga", "Bundesliga", "Ligue 1", "Altro"]) {
    assert.ok(leagueBadgeSvg(name).startsWith("<svg"));
  }
});
