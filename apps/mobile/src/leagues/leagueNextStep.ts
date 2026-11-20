import type { LeagueNextStepTarget } from "@fantappero/contracts";
import type { AppTabParamList } from "../navigation/types";

/**
 * Dove porta, nell'app, il «Prossimo passo» della home lega (`leagueHomeNextStep` di
 * `@fantappero/contracts`, lo stesso del web). Prima di andarci la home rende attiva la sua
 * lega, come fa il web con `?lega=`.
 *
 * Solo logica pura e import di tipo: gira nei test `node:test` senza il bundle di
 * `@fantappero/contracts`.
 */
export type LeagueNextStepRoute =
  | { kind: "admin" }
  | { kind: "tab"; screen: keyof AppTabParamList };

export function leagueNextStepRoute(target: LeagueNextStepTarget): LeagueNextStepRoute {
  switch (target) {
    case "admin":
      return { kind: "admin" };
    case "roster":
      return { kind: "tab", screen: "Roster" };
    case "auction":
      return { kind: "tab", screen: "Auction" };
    case "formation":
      return { kind: "tab", screen: "Formation" };
    case "standings":
      return { kind: "tab", screen: "Standings" };
  }
}
