import { isNewerAppVersion, type AndroidAppVersion } from "@fantappero/contracts";
import { useCallback, useEffect, useRef, useState } from "react";
import { AppState, Platform } from "react-native";
import { fetchAppVersion } from "../api/appVersion";
import { installedAndroidVersionCode } from "./installedVersion";
import { isReturnToForeground, shouldRefreshAppVersion, updateBannerVersion } from "./updateBanner";

/**
 * Ultima risposta del server, fuori dal componente: il cambio tema rimonta la navigazione e
 * non deve far ripartire la richiesta. Legata all'utente: un altro accesso la richiede di nuovo.
 */
let lastResult: { userId: string; fetchedAt: number; latest: AndroidAppVersion | null } | null =
  null;

/**
 * «Più tardi» (release 1.4): vale fino al prossimo avvio o ritorno in primo piano. Fuori dal
 * componente per la stessa ragione di `lastResult` (il cambio tema non lo deve riproporre);
 * all'avvio dell'app il modulo riparte da capo e l'avviso torna.
 */
let dismissedThisVisit: number | null = null;

/**
 * Avviso «È disponibile la versione X dell'app» (release 1.4, Rosario 23/11): legge la versione
 * pubblicata a ogni avvio dopo l'accesso e a ogni ritorno in primo piano (al più una volta al
 * minuto) e la ripropone finché l'app non è aggiornata. Gli errori non mostrano nulla.
 */
export function useAppUpdateBanner(
  accessToken: string | null | undefined,
  userId: string | null | undefined,
): { version: AndroidAppVersion | null; dismiss: () => void } {
  const [latest, setLatest] = useState<AndroidAppVersion | null>(() =>
    lastResult && lastResult.userId === userId ? lastResult.latest : null,
  );
  const [dismissedCode, setDismissedCode] = useState<number | null>(() => dismissedThisVisit);
  const tokenRef = useRef(accessToken);
  tokenRef.current = accessToken;
  const inFlight = useRef(false);
  const appState = useRef<string | null>(AppState.currentState ?? null);

  const refresh = useCallback(() => {
    const token = tokenRef.current;
    if (Platform.OS !== "android" || !token || !userId || inFlight.current) {
      return;
    }
    const cached = lastResult && lastResult.userId === userId ? lastResult : null;
    if (cached) {
      setLatest(cached.latest);
    }
    if (!shouldRefreshAppVersion(cached?.fetchedAt ?? null, Date.now())) {
      return;
    }
    inFlight.current = true;
    fetchAppVersion(token)
      .then((result) => {
        lastResult = { userId, fetchedAt: Date.now(), latest: result.android ?? null };
        setLatest(lastResult.latest);
      })
      .catch(() => undefined)
      .finally(() => {
        inFlight.current = false;
      });
  }, [userId]);

  useEffect(() => {
    refresh();
    const subscription = AppState.addEventListener("change", (next) => {
      const previous = appState.current;
      appState.current = next;
      if (isReturnToForeground(previous, next)) {
        // Nuovo ingresso nell'app: «Più tardi» non vale più e si richiede la versione.
        dismissedThisVisit = null;
        setDismissedCode(null);
        refresh();
      }
    });
    return () => subscription.remove();
  }, [accessToken, refresh]);

  const version = updateBannerVersion(
    {
      platformOS: Platform.OS,
      signedIn: Boolean(accessToken && userId),
      installedVersionCode: installedAndroidVersionCode(),
      latest,
      dismissedVersionCode: dismissedCode,
    },
    isNewerAppVersion,
  );

  const dismiss = useCallback(() => {
    if (!latest) {
      return;
    }
    dismissedThisVisit = latest.latestVersionCode;
    setDismissedCode(latest.latestVersionCode);
  }, [latest]);

  return { version, dismiss };
}
