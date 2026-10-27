import type { NotificationEventPreference } from "@fantappero/contracts";
import { Switch, UiStatePanel } from "@fantappero/ui";
import { useCallback, useEffect, useState } from "react";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { fetchNotificationPreferences, updateNotificationPreference } from "../api/notifications";

const GROUPS: Array<{ category: "calciatori" | "sistema"; title: string; hint: string }> = [
  { category: "calciatori", title: "Calciatori", hint: "Per i calciatori della tua rosa e della tua formazione." },
  { category: "sistema", title: "Sistema", hint: "Scambi, asta, formazione e comunicazioni." },
];

const EVENT_GLYPH: Record<string, string> = {
  "calciatori.gol": "⚽",
  "calciatori.assist": "🅰",
  "calciatori.ammonizione": "🟨",
  "calciatori.espulsione": "🟥",
  "calciatori.sostituzione": "🔁",
  "calciatori.infortunio": "🩹",
  "calciatori.squalifica": "⛔",
  "sistema.scambi": "⇄",
  "sistema.asta": "🔨",
  "sistema.formazione": "⏰",
  "sistema.turno_omologato": "🏁",
  "sistema.avvisi_operatori": "📣",
};

/** Centro notifiche personale: ogni evento, canali in-app e push separati. */
export function NotificationEventSettings() {
  const [events, setEvents] = useState<NotificationEventPreference[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = loadStoredSession()?.accessToken;
    if (!token) {
      return;
    }
    try {
      const result = await fetchNotificationPreferences(token);
      setEvents(result.events ?? []);
    } catch (e) {
      setError(getApiErrorMessage(e, "Impossibile caricare le preferenze notifiche."));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function change(
    changes: Array<{ eventKey: string; inAppEnabled?: boolean; pushEnabled?: boolean }>,
  ) {
    const token = loadStoredSession()?.accessToken;
    if (!token || !events) {
      return;
    }
    const previous = events;
    setError(null);
    setBusy(changes[0]?.eventKey ?? null);
    setEvents(
      events.map((row) => {
        const hit = changes.find((c) => c.eventKey === row.eventKey);
        return hit
          ? {
              ...row,
              inAppEnabled: hit.inAppEnabled ?? row.inAppEnabled,
              pushEnabled: hit.pushEnabled ?? row.pushEnabled,
            }
          : row;
      }),
    );
    try {
      let latest = null;
      for (const c of changes) {
        latest = await updateNotificationPreference(token, c);
      }
      if (latest?.events) {
        setEvents(latest.events);
      }
    } catch (e) {
      setEvents(previous);
      setError(getApiErrorMessage(e, "Preferenza non salvata."));
    } finally {
      setBusy(null);
    }
  }

  if (error && !events) {
    return <UiStatePanel state="error" title="Centro notifiche non disponibile" message={error} />;
  }
  if (!events) {
    return <UiStatePanel state="loading" title="Centro notifiche" message="Caricamento preferenze…" />;
  }

  return (
    <div className="fa-notif-settings" data-testid="notification-event-settings">
      <p className="fa-field__hint">
        Scegli quali notifiche ricevere, evento per evento: nel centro notifiche e come push sul
        telefono. Le email restano solo per registrazione e comunicazioni importanti.
      </p>
      {error ? <p className="fa-field__error">{error}</p> : null}
      {GROUPS.map((group) => {
        const rows = events.filter((row) => row.category === group.category);
        if (rows.length === 0) {
          return null;
        }
        return (
          <section key={group.category} className="fa-notif-settings__group">
            <header className="fa-notif-settings__head">
              <h4>{group.title}</h4>
              <p>{group.hint}</p>
              <span className="fa-notif-settings__bulk">
                <button
                  type="button"
                  onClick={() =>
                    void change(rows.map((r) => ({ eventKey: r.eventKey, inAppEnabled: true, pushEnabled: true })))
                  }
                >
                  Attiva tutte
                </button>
                <button
                  type="button"
                  onClick={() =>
                    void change(rows.map((r) => ({ eventKey: r.eventKey, inAppEnabled: false, pushEnabled: false })))
                  }
                >
                  Disattiva tutte
                </button>
              </span>
            </header>
            <div className="fa-notif-settings__cols" aria-hidden="true">
              <span />
              <span />
              <span>In app</span>
              <span>Push</span>
            </div>
            <ul className="fa-notif-settings__list">
              {rows.map((row) => (
                <li key={row.eventKey} className="fa-notif-settings__row">
                  <span className="fa-notif-settings__glyph" aria-hidden="true">
                    {EVENT_GLYPH[row.eventKey] ?? "🔔"}
                  </span>
                  <strong>{row.label}</strong>
                  <Switch
                    checked={row.inAppEnabled}
                    disabled={busy === row.eventKey}
                    onCheckedChange={(on) => void change([{ eventKey: row.eventKey, inAppEnabled: on }])}
                    ariaLabel={`${row.label}: in app`}
                    testId={`notif-event-${row.eventKey}-inapp`}
                  />
                  <Switch
                    checked={row.pushEnabled}
                    disabled={busy === row.eventKey}
                    onCheckedChange={(on) => void change([{ eventKey: row.eventKey, pushEnabled: on }])}
                    ariaLabel={`${row.label}: push`}
                    testId={`notif-event-${row.eventKey}-push`}
                  />
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
