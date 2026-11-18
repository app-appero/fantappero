import { StackActions, type NavigationContainerRefWithCurrent } from "@react-navigation/native";
import * as Linking from "expo-linking";
import { useEffect, useRef } from "react";
import { useAuthSession } from "../session/DemoSessionContext";
import { type AppLinkRoute, planAppLink, routeForAppLinkUrl } from "./deepLinks";
import type { RootStackParamList } from "./types";

type Props = { navigationRef: NavigationContainerRefWithCurrent<RootStackParamList> };

/**
 * Apre la schermata di un link (`deepLinks.ts`) quando la sessione è pronta.
 * L'invito ricevuto prima dell'accesso resta in attesa e si apre subito dopo il login.
 */
export function AppLinkHandler({ navigationRef }: Props) {
  const { isAuthenticated, loading } = useAuthSession();
  const queued = useRef<AppLinkRoute | null>(null);
  const pendingAfterLogin = useRef<AppLinkRoute | null>(null);
  const sessionRef = useRef({ isAuthenticated, loading });
  sessionRef.current = { isAuthenticated, loading };

  useEffect(() => {
    const receive = (url: string | null) => {
      const route = routeForAppLinkUrl(url);
      if (!route) {
        return;
      }
      queued.current = route;
      flush();
    };
    const subscription = Linking.addEventListener("url", (event) => receive(event.url));
    void Linking.getInitialURL().then(receive);
    return () => subscription.remove();
    // flush legge sempre lo stato corrente da sessionRef.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    flush();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, loading]);

  function flush() {
    const session = sessionRef.current;
    if (session.loading) {
      return;
    }
    if (session.isAuthenticated && pendingAfterLogin.current && !queued.current) {
      queued.current = pendingAfterLogin.current;
      pendingAfterLogin.current = null;
    }
    const route = queued.current;
    if (!route) {
      return;
    }
    queued.current = null;
    const plan = planAppLink(route, session.isAuthenticated);
    if (plan.kind === "after-login") {
      pendingAfterLogin.current = plan.route;
      return;
    }
    if (plan.kind === "open") {
      open(plan.route);
    }
  }

  function open(route: AppLinkRoute, attempt = 0) {
    // Dopo login/logout lo stack si rimonta: si aspetta che abbia la schermata giusta.
    const state = navigationRef.isReady() ? navigationRef.getRootState() : undefined;
    if (!state?.routeNames?.includes(route.name)) {
      if (attempt < 20) {
        setTimeout(() => open(route, attempt + 1), 100);
      }
      return;
    }
    navigationRef.dispatch(StackActions.push(route.name, route.params));
  }

  return null;
}
