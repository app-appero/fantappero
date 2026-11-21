import { isNewerAppVersion, type AndroidAppVersion } from "@fantappero/contracts";
import { useCallback, useEffect, useRef, useState } from "react";
import { AppState, Platform } from "react-native";
import { fetchAppVersion } from "../api/appVersion";
import { loadDismissedVersionCode, saveDismissedVersionCode } from "./dismissedVersionStorage";
import { installedAndroidVersionCode } from "./installedVersion";
import { shouldRefreshAppVersion, updateBannerVersion } from "./updateBanner";

/**
 * Ultima risposta del server, fuori dal componente: il cambio tema rimonta la navigazione e
 * non deve far ripartire la richiesta. Legata all'utente: un altro accesso la richiede di nuovo.
 */
let lastResult: { userId: string; fetchedAt: number; latest: AndroidAppVersion | null } | null =
  null;

/**
 * Avviso «È disponibile la versione X dell'app»: legge la versione pubblicata all'avvio dopo
 * l'accesso e al ritorno in primo piano (al più ogni 3 ore). Gli errori non mostrano nulla.
 */
export function useAppUpdateBanner(
  accessToken: string | null | undefined,
  userId: string | null | undefined,
): { version: AndroidAppVersion | null; dismiss: () => void } {
  const [latest, setLatest] = useState<AndroidAppVersion | null>(() =>
    lastResult && lastResult.userId === userId ? lastResult.latest : null,
  );
  // `undefined` finché non si è letto il «Più tardi» salvato: niente avviso che poi sparisce.
  const [dismissedCode, setDismissedCode] = useState<number | null | undefined>(undefined);
  const tokenRef = useRef(accessToken);
  tokenRef.current = accessToken;
  const inFlight = useRef(false);

  const refresh = useCallback(() => {
    const token = tokenRef.current;
    if (Platform.OS !== "android" || !token || !userId || inFlight.current) {
      return;
    }
    const cached = lastResult && lastResult.userId === userId ? lastResult : null;
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
    if (Platform.OS !== "android") {
      return;
    }
    let active = true;
    loadDismissedVersionCode()
      .then((code) => active && setDismissedCode(code))
      .catch(() => active && setDismissedCode(null));
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    refresh();
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") {
        refresh();
      }
    });
    return () => subscription.remove();
  }, [accessToken, refresh]);

  const version =
    dismissedCode === undefined
      ? null
      : updateBannerVersion(
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
    setDismissedCode(latest.latestVersionCode);
    void saveDismissedVersionCode(latest.latestVersionCode).catch(() => undefined);
  }, [latest]);

  return { version, dismiss };
}
