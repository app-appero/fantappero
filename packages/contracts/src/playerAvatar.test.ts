import assert from "node:assert/strict";
import { test } from "node:test";
import { clubKit, hasClubKit, playerAvatarSvg, playerAvatarUrl } from "./playerAvatar.ts";

test("nomi dei provider diversi trovano la stessa maglia", () => {
  assert.equal(clubKit("Inter").primary, clubKit("Internazionale").primary);
  assert.equal(clubKit("AC Milan").pattern, "stripes");
  assert.equal(clubKit("Paris Saint Germain").pattern, "band");
  assert.equal(clubKit("Borussia Monchengladbach").primary, clubKit("Gladbach").primary);
  assert.equal(clubKit("Atlético Madrid").pattern, "stripes");
  assert.ok(hasClubKit("Wolves"));
});

test("club sconosciuto o assente: maglia neutra, nessun errore", () => {
  assert.equal(hasClubKit("Club Inventato"), false);
  assert.equal(hasClubKit(null), false);
  assert.ok(playerAvatarSvg("a1", null).startsWith("<svg"));
});

test("l'avatar è stabile per lo stesso calciatore e diverso tra calciatori", () => {
  assert.equal(playerAvatarSvg("x1", "Inter"), playerAvatarSvg("x1", "Inter"));
  assert.notEqual(playerAvatarSvg("x1", "Inter"), playerAvatarSvg("x2", "Inter"));
  assert.ok(playerAvatarUrl("x1", "Inter").startsWith("data:image/svg+xml"));
});

test("tutti i 96 club dei 5 campionati 2025/26 hanno la maglia", () => {
  const clubs = [
    "Atalanta","Bologna","Cagliari","Como","Cremonese","Fiorentina","Genoa","Hellas Verona","Inter","Juventus","Lazio","Lecce","AC Milan","Napoli","Parma","Pisa","AS Roma","Sassuolo","Torino","Udinese",
    "Arsenal","Aston Villa","Bournemouth","Brentford","Brighton","Burnley","Chelsea","Crystal Palace","Everton","Fulham","Leeds","Liverpool","Manchester City","Manchester United","Newcastle","Nottingham Forest","Sunderland","Tottenham","West Ham","Wolves",
    "Alaves","Athletic Club","Atletico Madrid","Barcelona","Celta Vigo","Elche","Espanyol","Getafe","Girona","Levante","Mallorca","Osasuna","Real Oviedo","Rayo Vallecano","Real Betis","Real Madrid","Real Sociedad","Sevilla","Valencia","Villarreal",
    "FC Augsburg","Union Berlin","Werder Bremen","Borussia Dortmund","Eintracht Frankfurt","SC Freiburg","Hamburger SV","FC Heidenheim","Hoffenheim","FC Koln","Mainz","Borussia Monchengladbach","Bayern Munich","RB Leipzig","St Pauli","VfB Stuttgart","VfL Wolfsburg","Bayer Leverkusen",
    "Angers","Auxerre","Brest","Le Havre","Lens","Lille","Lorient","Lyon","Marseille","Metz","Monaco","Nantes","Nice","Paris FC","Paris Saint Germain","Rennes","Strasbourg","Toulouse",
  ];
  assert.equal(clubs.length, 96);
  const missing = clubs.filter((club) => !hasClubKit(club));
  assert.deepEqual(missing, []);
});
