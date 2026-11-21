/**
 * Nome della schermata davvero a fuoco in tutto l'albero di navigazione (stack radice, tab,
 * pannello admin), per il contesto di «Segnala un problema».
 *
 * Solo logica pura senza import: gira nei test `node:test`. Lo stato arriva dal
 * `NavigationContainer` radice (`onReady` / `onStateChange`), che lo ricostruisce leggendo
 * anche i navigator annidati: così vale per ogni strada (menu, Home lega, notifiche, link)
 * e per le schermate dello stack sopra le tab (es. Home lega).
 */

export type RouteStateLike = {
  name: string;
  state?: NavigationStateLike;
};

export type NavigationStateLike = {
  index?: number;
  type?: string;
  routes: readonly RouteStateLike[];
};

/** Route che contengono un navigator: senza il loro stato la schermata vera non si conosce. */
export const NAVIGATOR_ROUTE_NAMES: readonly string[] = ["MainTabs", "AdminPanel"];

function focusedChild(state: NavigationStateLike): RouteStateLike | undefined {
  if (typeof state.index === "number") {
    return state.routes[state.index];
  }
  // Stato parziale: in uno stack la schermata a fuoco è l'ultima; negli altri navigator
  // dipenderebbe dalla route iniziale, che qui non si conosce.
  return state.type === "stack" ? state.routes[state.routes.length - 1] : undefined;
}

/**
 * Schermata più interna a fuoco; `undefined` se non si sa con certezza (mai un valore di
 * ripiego come la tab iniziale).
 */
export function focusedRouteName(
  state: NavigationStateLike | undefined,
  navigatorRoutes: readonly string[] = NAVIGATOR_ROUTE_NAMES,
): string | undefined {
  let current = state;
  while (current) {
    const route = focusedChild(current);
    if (!route) {
      return undefined;
    }
    if (route.state) {
      current = route.state;
      continue;
    }
    return navigatorRoutes.includes(route.name) ? undefined : route.name;
  }
  return undefined;
}
