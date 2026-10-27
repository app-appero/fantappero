import type { NotificationItem } from "@fantappero/contracts";
import type { AppTabParamList, RootStackParamList } from "./types";

export type NotificationRoute =
  | { kind: "stack"; name: keyof RootStackParamList }
  | { kind: "matchup"; slotId: string }
  | { kind: "tab"; screen: keyof AppTabParamList };

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
  "Lotto aggiudicato",
  "Sei stato sorpassato",
  "Asta a rilanci iniziata",
]);

/** Percorsi web (deep link del payload) → schermata mobile equivalente. */
const PATH_ROUTES: Array<[RegExp, NotificationRoute]> = [
  [/^\/$/, { kind: "stack", name: "LeagueHome" }],
  [/^\/inviti/, { kind: "stack", name: "ReceivedInvites" }],
  [/^\/formazione/, { kind: "tab", screen: "Formation" }],
  [/^\/classifica/, { kind: "tab", screen: "Standings" }],
  [/^\/turni/, { kind: "tab", screen: "Matchday" }],
  [/^\/rosa/, { kind: "tab", screen: "Roster" }],
  [/^\/asta/, { kind: "tab", screen: "Auction" }],
  [/^\/svincolati/, { kind: "tab", screen: "Waiver" }],
  [/^\/scambi/, { kind: "tab", screen: "Market" }],
  [/^\/profilo/, { kind: "tab", screen: "Profile" }],
];

/** Destinazione mobile di una notifica, o `null` se non c'è una meta. */
export function resolveNotificationRoute(
  item: Pick<NotificationItem, "deepLink" | "title">,
): NotificationRoute | null {
  // Gli scambi e le aste condividono il percorso web «/mercato»: sull'app hanno schermate diverse.
  if (TRADE_TITLES.has(item.title)) {
    return { kind: "tab", screen: "Market" };
  }
  if (AUCTION_TITLES.has(item.title)) {
    return { kind: "tab", screen: "Auction" };
  }
  const link = (item.deepLink ?? "").trim();
  if (link.startsWith("/") && !link.startsWith("//") && !link.includes("://")) {
    const path = link.split(/[?#]/)[0] ?? link;
    const matchup = /^\/turni\/scontro\/([^/]+)\/?$/.exec(path);
    if (matchup?.[1]) {
      return { kind: "matchup", slotId: decodeURIComponent(matchup[1]) };
    }
    if (/^\/mercato/.test(path)) {
      return { kind: "tab", screen: "Roster" };
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
