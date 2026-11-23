import {
  appUsageGroupHint,
  appUsageGroupTitle,
  appUsageSummaryLine,
  appUsageUserName,
  appUsageUserSeen,
  type AdminAppUsage,
  type AdminAppUsageGroup,
} from "@fantappero/contracts";
import { useEffect, useState } from "react";
import { fetchAppVersionUsers } from "../api/admin";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";

function groupKey(group: AdminAppUsageGroup): string {
  return `${group.kind}-${group.platform ?? ""}-${group.versionCode ?? ""}-${group.versionName ?? ""}`;
}

/**
 * «Chi ha quale versione» della pagina «Versione app» (release 1.4, decisione di Rosario del
 * 23/11): un gruppo per versione esatta (dalla 1.4 l'app la manda), poi le app 1.2-1.3 e quelle
 * più vecchie (versione non nota), poi chi non ha mai usato l'app. Stessi testi dell'app
 * (`@fantappero/contracts`). «App mai usata / solo sito» parte chiuso perché è il più lungo.
 *
 * `reloadKey` cambia dopo un salvataggio del modulo: l'elenco si rilegge.
 */
export function AdminAppUsagePanel({ reloadKey = 0, now }: { reloadKey?: number; now?: Date }) {
  const [usage, setUsage] = useState<AdminAppUsage | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const session = loadStoredSession();
    if (!session?.accessToken) {
      return;
    }
    let active = true;
    fetchAppVersionUsers(session.accessToken)
      .then((result) => {
        if (active) {
          setUsage(result);
          setError(null);
        }
      })
      .catch((cause) => {
        if (active) {
          setError(getApiErrorMessage(cause, "Impossibile leggere chi ha quale versione."));
        }
      });
    return () => {
      active = false;
    };
  }, [reloadKey]);

  const at = now ?? new Date();

  return (
    <section
      className="fa-admin-appusage"
      aria-labelledby="admin-appusage-title"
      data-testid="admin-appversion-users"
    >
      <h2 id="admin-appusage-title">Chi ha quale versione</h2>
      {error ? (
        <p role="alert" className="fa-field__error">
          {error}
        </p>
      ) : null}
      {!usage && !error ? <p className="fa-admin-appusage__hint">Caricamento…</p> : null}
      {usage ? (
        <>
          <p className="fa-admin-appusage__summary" data-testid="admin-appversion-users-summary">
            {usage.announced
              ? appUsageSummaryLine(usage)
              : `${usage.appUsers} ${usage.appUsers === 1 ? "utente usa" : "utenti usano"} l'app`}
            {` · ${usage.totalUsers} ${usage.totalUsers === 1 ? "utente" : "utenti"} in tutto`}
          </p>
          {usage.groups.map((group) => {
            const hint = appUsageGroupHint(group);
            return (
              <details
                key={groupKey(group)}
                className="fa-admin-appusage__group"
                open={group.kind !== "never"}
                data-testid={`admin-appversion-group-${group.kind}`}
              >
                <summary>
                  <span className="fa-admin-appusage__title">{appUsageGroupTitle(group)}</span>
                  {group.upToDate ? (
                    <span className="fa-admin-appusage__badge">aggiornati</span>
                  ) : null}
                </summary>
                {hint ? <p className="fa-admin-appusage__hint">{hint}</p> : null}
                <ul className="fa-admin-appusage__users">
                  {group.users.map((user) => {
                    const seen = appUsageUserSeen(user, at);
                    return (
                      <li key={user.userId}>
                        <strong>{appUsageUserName(user)}</strong>
                        <span className="fa-admin-appusage__email">{user.email}</span>
                        {seen ? <span className="fa-admin-appusage__seen">{seen}</span> : null}
                      </li>
                    );
                  })}
                </ul>
              </details>
            );
          })}
        </>
      ) : null}
    </section>
  );
}
