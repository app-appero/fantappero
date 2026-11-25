import type { LeagueSummary, NotificationItem } from "@fantappero/contracts";
import type { AdminStackParamList, AppTabParamList, RootStackParamList } from "./types";

export type NotificationRoute =
  | { kind: "stack"; name: keyof RootStackParamList; params?: Record<string, string> }
  | { kind: "matchup"; slotId: string }
  | { kind: "tab"; screen: keyof AppTabParamList; params?: Record<string, string> }
  | { kind: "admin"; screen: keyof AdminStackParamList }
  // Link esterno da aprire nel browser: il download della nuova versione dell'app (1.4).
  | { kind: "external"; url: string };

/** Solo https, con un dominio e senza spazi: come `isHttpsDownloadUrl` dei contratti. */
const EXTERNAL_HTTPS_LINK = /^https:\/\/[^\s/?#:@]+(:\d+)?([/?#]\S*)?$/;
/** Titolo della notifica della nuova versione (backend, template `sistema.versione_app`). */
const APP_UPDATE_TITLE = /^È disponibile (la versione \S+|una nuova versione) dell'app$/;

const TRADE_TITLES = new Set([
  "Nuova proposta di scambio",
  "Scambio accettato",
  "Scambio in attesa di approvazione",
  "Scambio rifiutato",
  "Controproposta ricevuta",
  "Scambio approvato",
  "Scambio rifiutato dall'amministratore",
  "Aggiornamento scambio",
]);

const AUCTION_TITLES = new Set([
  "Busta aggiudicata",
  "Busta non aggiudicata",
  "Spareggio aperto",
  "Spareggio annullato",
  "Lotto aggiudicato",
  "Sei stato sorpassato",
  "Scelta richiesta: rosa al completo",
  "Asta a rilanci iniziata",
  "Lotto perso: crediti insufficienti",
  "Lotto perso: rosa al completo",
]);

/** Valore di un parametro di query nel deep link (es. "?scambio=<id>"), o `null`. */
function extractQueryParam(deepLink: string | null | undefined, key: string): string | null {
  const link = (deepLink ?? "").trim();
  const queryIndex = link.indexOf("?");
  if (queryIndex === -1) {
    return null;
  }
  const params = new URLSearchParams(link.slice(queryIndex + 1));
  const value = params.get(key);
  return value ? value : null;
}

/** Percorsi web (deep link del payload) → schermata mobile equivalente. */
const PATH_ROUTES: Array<[RegExp, NotificationRoute]> = [
  // Nuova segnalazione utente: la notifica arriva solo agli operatori.
  [/^\/admin\/feedback/, { kind: "admin", screen: "AdminFeedback" }],
  // Nuova richiesta di accesso al pilota (solo operatori): pannello utenti e richieste tester.
  [/^\/admin\/utenti/, { kind: "admin", screen: "AdminUsers" }],
  [/^\/admin\/leghe/, { kind: "admin", screen: "AdminLeagues" }],
  [/^\/admin\/notifiche/, { kind: "admin", screen: "AdminNotifications" }],
  [/^\/admin\/?$/, { kind: "admin", screen: "AdminHome" }],
  // Aggiornamento di stato di una propria segnalazione.
  [/^\/feedback/, { kind: "stack", name: "Feedback" }],
  [/^\/$/, { kind: "stack", name: "LeagueHome" }],
  [/^\/inviti/, { kind: "stack", name: "ReceivedInvites" }],
  // Esito di un invito nominativo e nuovo partecipante: directory fantallenatori della lega.
  [/^\/fantallenatori/, { kind: "stack", name: "ManagerDirectory" }],
  [/^\/formazione/, { kind: "tab", screen: "Formation" }],
  [/^\/classifica/, { kind: "tab", screen: "Standings" }],
  [/^\/turni/, { kind: "tab", screen: "Matchday" }],
  [/^\/rosa/, { kind: "tab", screen: "Roster" }],
  // «/asta-live» deve precedere «/asta», che altrimenti lo intercetterebbe: le notifiche
  // dell'asta a rilanci aprono la scheda «Live», quelle delle buste chiuse «Buste chiuse».
  [/^\/asta-live/, { kind: "tab", screen: "Auction", params: { modalita: "live" } }],
  [/^\/asta/, { kind: "tab", screen: "Auction", params: { modalita: "buste" } }],
  // Esiti degli svincolati (link «/svincolati»); «/svincoli» è la pagina web equivalente.
  [/^\/svincolati/, { kind: "tab", screen: "Waiver" }],
  [/^\/svincoli/, { kind: "tab", screen: "Waiver" }],
  [/^\/scambi/, { kind: "tab", screen: "Market" }],
  [/^\/profilo/, { kind: "tab", screen: "Profile" }],
];

/** Destinazione mobile di una notifica, o `null` se non c'è una meta. */
export function resolveNotificationRoute(
  item: Pick<NotificationItem, "deepLink" | "title">,
): NotificationRoute | null {
  // «È disponibile la versione X dell'app» (release 1.4): il link è il download dell'APK. È
  // l'unica notifica che apre un link esterno; per le altre un link esterno non apre nulla.
  const external = (item.deepLink ?? "").trim();
  if (APP_UPDATE_TITLE.test(item.title) && EXTERNAL_HTTPS_LINK.test(external)) {
    return { kind: "external", url: external };
  }
  // Gli scambi e le aste condividono il percorso web «/mercato»: sull'app hanno schermate diverse.
  // Il titolo v2 è dinamico (interpola il nome della squadra avversaria, es. "Squadra X ti
  // propone uno scambio") e non combacia mai con TRADE_TITLES: il segnale affidabile è il
  // parametro ?scambio= nel deep link, presente su ogni notifica di scambio reale; il titolo
  // statico resta un fallback per eventuali notifiche più vecchie già in coda senza quel parametro.
  const proposalId = extractQueryParam(item.deepLink, "scambio");
  if (proposalId || TRADE_TITLES.has(item.title)) {
    return proposalId
      ? { kind: "tab", screen: "Market", params: { scambio: proposalId } }
      : { kind: "tab", screen: "Market" };
  }
  const link = (item.deepLink ?? "").trim();
  const isInternalLink = link.startsWith("/") && !link.startsWith("//") && !link.includes("://");
  const path = isInternalLink ? (link.split(/[?#]/)[0] ?? link) : "";
  // Il titolo d'asta è solo un fallback (es. notifiche vecchie con «/mercato»): se il deep
  // link punta già a «/asta» o «/asta-live» decide PATH_ROUTES, che sceglie anche la scheda.
  if (AUCTION_TITLES.has(item.title) && !/^\/asta/.test(path)) {
    return { kind: "tab", screen: "Auction" };
  }
  if (isInternalLink) {
    const matchup = /^\/turni\/scontro\/([^/]+)\/?$/.exec(path);
    if (matchup?.[1]) {
      return { kind: "matchup", slotId: decodeURIComponent(matchup[1]) };
    }
    if (/^\/mercato/.test(path)) {
      return { kind: "tab", screen: "Roster" };
    }
    // «Scegli il sostituto dopo lo scambio» (1.5, `/rosa?sostituto=1`): Rosa con la scelta aperta.
    if (/^\/rosa/.test(path) && extractQueryParam(item.deepLink, "sostituto") === "1") {
      return { kind: "tab", screen: "Roster", params: { sostituto: "1" } };
    }
    // «La lega è al completo: puoi aprire il mercato» (20/11): l'amministrazione della lega
    // della notifica, che la schermata rende attiva.
    if (/^\/lega\/amministrazione/.test(path)) {
      const leagueId = extractQueryParam(item.deepLink, "lega");
      return leagueId
        ? { kind: "stack", name: "LeagueAdmin", params: { leagueId } }
        : { kind: "stack", name: "LeagueAdmin" };
    }
    for (const [pattern, route] of PATH_ROUTES) {
      if (pattern.test(path)) {
        return route;
      }
    }
  }
  if (item.title === "Nuovo invito a una lega") {
    return { kind: "stack", name: "ReceivedInvites" };
  }
  if (item.title === "Scadenza formazione in arrivo") {
    return { kind: "tab", screen: "Formation" };
  }
  if (item.title === "Turno omologato" || item.title === "Correzione al turno omologato") {
    return { kind: "tab", screen: "Standings" };
  }
  return null;
}

/** Cosa fare al tocco su una notifica: prima, se serve, cambiare lega; poi aprire `route`. */
export type NotificationOpenPlan = {
  route: NotificationRoute;
  /** Lega da rendere attiva prima di navigare, `null` se resta quella attiva. */
  switchToLeagueId: string | null;
};

/**
 * Tocco su una notifica (elenco in app o push): chi è in più leghe deve finire nella lega
 * dell'evento, non in quella attiva (Rosario 21/11). Le schede lavorano sulla lega attiva,
 * quindi prima si rende attiva la lega della notifica, come fa il web con `?lega=`.
 *
 * La lega è il parametro `lega` del deep link: il backend lo aggiunge a ogni notifica di lega,
 * e lo stesso deep link arriva nei dati della push (`data.deepLink`). Senza lega, con la lega
 * già attiva o con una lega di cui l'utente non fa più parte (lasciata, eliminata) non cambia
 * nulla: la notifica si apre nella lega attiva, come prima. `null` = nessuna meta.
 */
export function planNotificationOpen(
  item: Pick<NotificationItem, "deepLink" | "title">,
  session: { activeLeagueId: string | null; leagues: readonly Pick<LeagueSummary, "id">[] },
): NotificationOpenPlan | null {
  const route = resolveNotificationRoute(item);
  if (!route) {
    return null;
  }
  const link = (item.deepLink ?? "").trim();
  const isInternalLink = link.startsWith("/") && !link.startsWith("//") && !link.includes("://");
  const leagueId = isInternalLink ? extractQueryParam(link, "lega") : null;
  const switchToLeagueId =
    leagueId &&
    leagueId !== session.activeLeagueId &&
    session.leagues.some((league) => league.id === leagueId)
      ? leagueId
      : null;
  return { route, switchToLeagueId };
}

const TAB_NAMES: readonly (keyof AppTabParamList)[] = [
  "Matchday",
  "Standings",
  "Roster",
  "Formation",
  "Auction",
  "Waiver",
  "Market",
  "Profile",
];

/**
 * Tab da aprire dopo l'impersonificazione dall'elenco segnalazioni: quella in cui
 * l'utente ha visto il problema. Il contesto è il nome di una schermata dell'app
 * (es. "Formation") oppure un percorso web (es. "/formazione") se la segnalazione
 * arriva dal sito. `undefined` = tab iniziale.
 */
export function impersonationTab(
  pageContext: string | null | undefined,
): keyof AppTabParamList | undefined {
  const context = (pageContext ?? "").trim();
  const byName = TAB_NAMES.find((tab) => tab === context);
  if (byName) {
    return byName;
  }
  if (context.startsWith("/")) {
    const route = resolveNotificationRoute({ title: "", deepLink: context });
    return route?.kind === "tab" ? route.screen : undefined;
  }
  return undefined;
}
