// Genera la pagina «Lavori in corso» (public/index.html) e le immagini SVG (public/img).
// Avatar, stemmi e distintivi vengono dagli stessi generatori dell'app (packages/contracts),
// così la pagina resta coerente con il gioco. Uso: node --experimental-strip-types build.mjs
import { mkdirSync, writeFileSync } from "node:fs";
import { clubCrestSvg, leagueBadgeSvg, playerAvatarSvg } from "../../packages/contracts/src/playerAvatar.ts";

const PILOTA_URL = "https://pilota.fantappero.it";
const OUT = new URL("./public/", import.meta.url);
mkdirSync(new URL("./img/", OUT), { recursive: true });

const slug = (text) =>
  text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");

const written = new Set();
function writeImg(name, svg) {
  if (!written.has(name)) {
    writeFileSync(new URL(`./img/${name}`, OUT), svg);
    written.add(name);
  }
  return `img/${name}`;
}
const avatar = (name, club) => writeImg(`av-${slug(name)}.svg`, playerAvatarSvg(`lp-${name}`, club));
const crest = (club) => writeImg(`crest-${slug(club)}.svg`, clubCrestSvg(club));
const badge = (league) => writeImg(`league-${slug(league)}.svg`, leagueBadgeSvg(league));

// Top player verificati a novembre 2026 (giocano oggi in uno dei 5 campionati).
const LEAGUES = [
  ["Serie A", [["Lautaro Martínez", "Inter"], ["Nicolò Barella", "Inter"], ["Alessandro Bastoni", "Inter"], ["Scott McTominay", "Napoli"], ["Paulo Dybala", "Roma"]]],
  ["Premier League", [["Erling Haaland", "Manchester City"], ["Bukayo Saka", "Arsenal"], ["Declan Rice", "Arsenal"], ["Cole Palmer", "Chelsea"], ["Gianluigi Donnarumma", "Manchester City"]]],
  ["LaLiga", [["Kylian Mbappé", "Real Madrid"], ["Vinícius Júnior", "Real Madrid"], ["Lamine Yamal", "Barcelona"], ["Pedri", "Barcelona"], ["Raphinha", "Barcelona"]]],
  ["Bundesliga", [["Harry Kane", "Bayern Munich"], ["Jamal Musiala", "Bayern Munich"], ["Michael Olise", "Bayern Munich"], ["Serhou Guirassy", "Borussia Dortmund"], ["Patrik Schick", "Bayer Leverkusen"]]],
  ["Ligue 1", [["Achraf Hakimi", "Paris Saint Germain"], ["Ousmane Dembélé", "Paris Saint Germain"], ["Désiré Doué", "Paris Saint Germain"], ["Lassine Sinayoko", "Paris FC"], ["Elye Wahi", "Nice"]]],
];

// Formazione di esempio (3-4-3): [x %, y %, nome, club, ruolo, tono, countdown, bloccato]
const PITCH = [
  [50, 10, "Haaland", "Manchester City", "A", "g", "2g 03:25", false],
  [20, 13, "Mbappé", "Real Madrid", "A", "g", "1g 04:25", false],
  [80, 13, "Kane", "Bayern Munich", "A", "y", "2g 09:10", false],
  [13, 36, "Musiala", "Bayern Munich", "C", "", "09:10", true],
  [38, 33, "Pedri", "Barcelona", "C", "g", "1g 03:25", false],
  [62, 33, "Rice", "Arsenal", "C", "g", "2g 06:55", false],
  [87, 36, "Barella", "Inter", "C", "y", "2g 05:40", false],
  [22, 60, "Hakimi", "Paris Saint Germain", "D", "g", "2g 04:40", false],
  [50, 62, "Saliba", "Arsenal", "D", "", "1g 09:30", true],
  [78, 60, "Bastoni", "Inter", "D", "", "2g 05:40", false],
  [50, 86, "Donnarumma", "Manchester City", "P", "", "2g 05:40", false],
];

const CLUB_STRIP = ["Inter", "Milan", "Juventus", "Napoli", "Arsenal", "Liverpool", "Manchester City", "Real Madrid", "Barcelona", "Bayern Munich", "Borussia Dortmund", "Paris Saint Germain", "Marseille", "Atletico Madrid", "Roma", "Chelsea"];

const lockIcon = (s = 16) =>
  `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>`;

const logo = (s) =>
  `<svg class="logo" width="${s}" height="${s}" viewBox="0 0 64 64" role="img" aria-label="FantApperò"><defs><linearGradient id="lg" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#2748d8"/><stop offset="1" stop-color="#6a3fe0"/></linearGradient><clipPath id="lc"><rect width="64" height="64" rx="18"/></clipPath></defs><rect width="64" height="64" rx="18" fill="url(#lg)"/><g opacity=".18" clip-path="url(#lc)"><rect x="0" width="8" height="64" fill="#fff"/><rect x="16" width="8" height="64" fill="#fff"/><rect x="32" width="8" height="64" fill="#fff"/><rect x="48" width="8" height="64" fill="#fff"/></g><path d="M14 52L20.6 12H49L47.5 20.5H29.2L27.8 28.5H41.8L40.6 35.5H26.6L24.2 52Z" fill="#fff"/><circle cx="47" cy="46" r="8.5" fill="#ffd23f"/><path d="M47 42.2L50.7 44.8L49.3 49.1H44.7L43.3 44.8Z" fill="#2748d8"/><path d="M45.5 33L53 27" stroke="#ffd23f" stroke-width="3.6" stroke-linecap="round"/></svg>`;

const FAVICON = `data:image/svg+xml;utf8,${encodeURIComponent(logo(64).replace('class="logo" ', '').replace(/ role="img" aria-label="FantApperò"/, ""))}`;

const players = PITCH.map(([x, y, name, club, role, tone, cd, locked]) => {
  const label = name;
  return `<div class="pl pl--${tone || "n"} role-${role}" style="left:${x}%;top:${y}%"><span class="pl__ph"><img src="${avatar(name === "Mbappé" ? "Kylian Mbappé" : name, club)}" alt="" width="64" height="64">${locked ? `<i class="pl__lock">${lockIcon(11)}</i>` : ""}</span><b class="pl__n">${label}</b><small class="pl__c">${cd}</small></div>`;
}).join("");

const stripImgs = CLUB_STRIP.map((c) => `<img src="${crest(c)}" alt="" width="46" height="51" loading="lazy">`).join("");

const topCards = LEAGUES.map(([league, list]) => {
  const rows = list
    .map(([n, c]) => `<li><img class="av" src="${avatar(n, c)}" alt="" width="44" height="44" loading="lazy"><span>${n}</span><img class="cr" src="${crest(c)}" alt="" width="22" height="24" loading="lazy"></li>`)
    .join("");
  return `<article class="top"><header><img src="${badge(league)}" alt="" width="44" height="44"><h3>${league}</h3></header><ul>${rows}</ul></article>`;
}).join("");

const leagueBadges = LEAGUES.map(([l]) => `<img src="${badge(l)}" alt="${l}" width="34" height="34">`).join("");
const friendAvatars = ["Pedri", "Jamal Musiala", "Harry Kane", "Erling Haaland", "Kylian Mbappé"]
  .map((n) => {
    const club = LEAGUES.flatMap(([, l]) => l).find(([x]) => x === n || x.endsWith(n))?.[1] ?? "Inter";
    const full = LEAGUES.flatMap(([, l]) => l).find(([x]) => x === n || x.endsWith(n))?.[0] ?? n;
    return `<img src="${avatar(full, club)}" alt="" width="40" height="40">`;
  })
  .join("");

const FEATURES = [
  ["5 campionati,<br>una sola lega", "Serie A, Premier, LaLiga, Bundesliga e Ligue 1 nella stessa rosa: Haaland, Mbappé, Lautaro, Kane, Dembélé… tutti insieme.", `<div class="row">${leagueBadges}</div>`, "#7FA8FF"],
  ["Formazione a step", "Ogni calciatore si blocca al fischio della sua partita. Cambi finché puoi, poi 3 mosse tattiche.", `<div class="row"><span class="chip chip--brand">Sab 15:00</span><span class="chip chip--gold">${lockIcon(14)} bloccati</span><span class="chip chip--green">liberi</span></div>`, "#FFD23F"],
  ["Live minuto per minuto", "Gol, voti, sostituzioni: il bianco è definitivo, il blu è in campo, il viola è senza voto.", `<div class="row"><span class="chip chip--white">8,0</span><span class="chip chip--live">7,5 LIVE</span><span class="chip chip--sv">S.V.</span></div>`, "#60A5FA"],
  ["Asta, buste e scambi", "Costruisci la rosa con rilanci in diretta, offerte segrete e scambi con gli amici.", `<div class="row"><span class="chip chip--gold-s">🔨 Asta</span><span class="chip chip--sky">✉ Buste</span><span class="chip chip--violet">⇄ Scambi</span></div>`, "#B58CFF"],
  ["Leghe con gli amici", "Crea la tua lega privata, invita con un link o per nome, sfida la banda ogni giornata.", `<div class="row faces">${friendAvatars}</div>`, "#34D399"],
  ["Una mano da voi", "Hai trovato un bug o hai un'idea? La segnalazione parte dall'app, con foto o video, e segui lo stato.", `<div class="row"><span class="chip">Ricevuta</span><span class="chip chip--gold-s">In lavorazione</span><span class="chip chip--green">Risolta</span></div>`, "#FF8FB8"],
]
  .map(([t, d, v, c]) => `<article class="feat" style="--c:${c}"><h3>${t}</h3><p>${d}</p><div class="feat__v">${v}</div></article>`)
  .join("");

const ROAD = [
  ["Accesso con Google e profili", "ok"],
  ["Leghe private e inviti", "ok"],
  ["Asta, buste chiuse e scambi", "ok"],
  ["Formazione a step e mosse", "ok"],
  ["Live, voti e notifiche", "ok"],
  ["Fase pilota con i tester", "now"],
  ["Apertura al pubblico", "soon"],
];
const TAG = { ok: "Fatto", now: "In corso", soon: "Prossimamente" };
const ICON = { ok: "✓", now: "●", soon: "○" };
const road = ROAD.map(([t, s]) => `<li class="rm rm--${s}"><span class="rm__dot" aria-hidden="true">${ICON[s]}</span><b>${t}</b><small>${TAG[s]}</small></li>`).join("");

const STEPS = [
  ["1", "Entra con Google", "Apri pilota.fantappero.it e accedi con il tuo account"],
  ["2", "Crea o entra in una lega", "Con un codice, un link o un invito per nome"],
  ["3", "Gioca e segnala", "Schiera, segui il live e segnala ogni cosa strana"],
]
  .map(([n, t, d]) => `<li><b>${n}</b><div><strong>${t}</strong><span>${d}</span></div></li>`)
  .join("");

const CARDS = `<div class="pcards" aria-hidden="true"><div class="pc pc--b"><b>9,0</b><i>H</i><span>Haaland</span></div><div class="pc pc--v"><b>8,5</b><i>M</i><span>Mbappé</span></div><div class="pc pc--p"><b>8,0</b><i>K</i><span>Kane</span></div></div>`;

const html = `<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FantApperò Calcio · Lavori in corso — il fantacalcio che si gioca ogni minuto</title>
<meta name="description" content="Il fantacalcio che si gioca ogni minuto: 5 campionati, una sola lega, formazione a step e live. Stiamo finendo il cantiere: diventa tester della fase pilota.">
<meta name="theme-color" content="#0A0F22">
<meta property="og:title" content="FantApperò Calcio · Lavori in corso">
<meta property="og:description" content="5 campionati, una sola lega. Diventa tester della fase pilota su pilota.fantappero.it.">
<meta property="og:type" content="website">
<link rel="icon" href="${FAVICON}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:ital,wght@1,700;1,800&display=swap">
<link rel="stylesheet" href="styles.css">
</head>
<body>
<header class="nav">
  <a class="brand" href="#top" aria-label="FantApperò">${logo(44)}<span>FantApperò Calcio</span></a>
  <div class="nav__r"><span class="chip chip--wip"><i class="cone" aria-hidden="true">🚧</i> Lavori in corso</span><a class="btn btn--sm" href="${PILOTA_URL}">Diventa tester</a></div>
</header>
<main id="top">
<section class="hero">
  <div class="beam beam--l" aria-hidden="true"></div><div class="beam beam--r" aria-hidden="true"></div>
  <div class="hero__txt">
    <p class="kick"><span class="dot"></span>LAVORI IN CORSO</p>
    <h1>Il fantacalcio<br>che si gioca<br><em>ogni minuto</em></h1>
    <p class="lead">5 campionati. Una sola lega. Formazione a step, live minuto per minuto, asta e scambi con gli amici. Stiamo finendo il cantiere: <b>entra in campo per primo.</b></p>
    <div class="cta"><a class="btn btn--xl" href="${PILOTA_URL}">Diventa tester <span class="arrow">→</span> <span class="host">pilota.fantappero.it</span></a><a class="btn btn--ghost" href="#cosa">Cosa stiamo costruendo ↓</a></div>
    <ul class="ticks"><li>✓ Accesso con Google</li><li>✓ Gratis</li><li>✓ Niente password</li></ul>
  </div>
  <div class="hero__vis">
    <div class="dock" role="img" aria-label="Blocco tra 01:00:18, mosse usate 2 su 3">${lockIcon(18)}<span class="dock__t"><small>BLOCCO</small><b>01:00:18</b></span><span class="dock__m"><span class="chip chip--out">Mosse 2/3</span><span class="chip chip--fill">→ 3/3</span></span></div>
    <div class="pitch" role="img" aria-label="Formazione di esempio con campioni dei cinque campionati"><div class="pitch__in"><i class="pl-h"></i><i class="pl-c"></i><i class="pl-a"></i><i class="pl-b"></i>${players}</div></div>
    <div class="live"><span class="live__i">⚽</span><div><small>FantApperò Calcio · ora</small><b>Gol di Mbappé!</b><span>+3 nel tuo Leo FC</span></div></div>
    ${CARDS}
  </div>
  <div class="strip" aria-hidden="true"><div class="strip__in">${stripImgs}${stripImgs}</div></div>
</section>

<section class="sec tops">
  <p class="eyebrow">I TOP PLAYER DI OGNI CAMPIONATO</p>
  <h2>Schiera i migliori<br><em>d'Europa</em></h2>
  <p class="sub">Schiera una formazione con campioni di campionati diversi: un attaccante della Premier, un centrocampista della Bundesliga, un difensore della Ligue 1. Tutta Europa, nella stessa squadra.</p>
  <div class="tops__g">${topCards}</div>
</section>

<section class="sec" id="cosa">
  <p class="eyebrow">COSA STIAMO COSTRUENDO</p>
  <h2>Tutto il calcio.<br><em>Un'unica partita.</em></h2>
  <div class="feats">${FEATURES}</div>
</section>

<section class="sec road" aria-labelledby="lavori">
  <div class="hazard" aria-hidden="true"></div>
  <p class="eyebrow eyebrow--gold">🚧 CANTIERE APERTO</p>
  <h2 id="lavori">Lavori in corso</h2>
  <p class="sub">Il grosso è fatto: ora lo proviamo sul campo, con voi.</p>
  <ol class="rms">${road}</ol>
</section>

<section class="sec final" id="tester">
  <div class="beam beam--l" aria-hidden="true"></div><div class="beam beam--r" aria-hidden="true"></div>
  <div class="final__g">
    <div>
      <p class="eyebrow eyebrow--gold">PILOTA · POSTI LIMITATI</p>
      <h2>Entra in campo<br><em>prima di tutti</em></h2>
      <p class="sub sub--l">Diventa tester della fase pilota: prova il gioco in anteprima, aiutaci a rifinirlo e porta la tua squadra al debutto.</p>
      <ol class="steps">${STEPS}</ol>
    </div>
    <div class="ticket">
      <div class="ticket__top"><span class="brand">${logo(40)}<span>FantApperò Calcio</span></span><b class="tag">TESTER</b></div>
      <p class="ticket__t">Ingresso<br><em>fase pilota</em></p>
      <dl><div><dt>SETTORE</dt><dd>5 CAMPIONATI</dd></div><div><dt>POSTO</dt><dd>LA TUA LEGA</dd></div></dl>
      <div class="ticket__cut" aria-hidden="true"></div>
      <a class="btn btn--block" href="${PILOTA_URL}">Diventa tester <span class="arrow">→</span> <span class="host">pilota.fantappero.it</span></a>
      <p class="ticket__n">Accesso con Google · gratis · niente password</p>
    </div>
  </div>
</section>
</main>
<footer class="foot"><a class="brand" href="#top">${logo(34)}<span>FantApperò Calcio</span></a><span class="foot__l"><a href="${PILOTA_URL}">pilota.fantappero.it</a><a href="${PILOTA_URL}/privacy">Informativa privacy</a><span>© FantApperò Calcio</span></span></footer>
</body>
</html>
`;
writeFileSync(new URL("./index.html", OUT), html);
console.log(`ok: index.html + ${written.size} immagini`);
