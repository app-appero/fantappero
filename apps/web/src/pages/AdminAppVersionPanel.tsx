import {
  EMPTY_APP_VERSION_FORM,
  appVersionFormFrom,
  appVersionUpdateFrom,
  validateAppVersionForm,
  type AppVersionFormErrors,
  type AppVersionFormFields,
  type AppVersionInfo,
} from "@fantappero/contracts";
import { Button, Input } from "@fantappero/ui";
import { useEffect, useState } from "react";
import { fetchAppVersionConfig, saveAppVersionConfig } from "../api/admin";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";

// Controlli e testi dei campi in comune con l'app (`@fantappero/contracts`, release 1.4).
type Fields = AppVersionFormFields;
type FieldErrors = AppVersionFormErrors;

/**
 * Pannello operatore: ultima versione dell'APK Android, annunciata a chi ha un'app più vecchia.
 * Dalla 1.4 sta nella pagina «Versione app» (`AdminAppVersionPage`), che ha già il suo titolo:
 * lì il titolo della sezione resta solo per i lettori di schermo (`hideTitle`).
 */
export function AdminAppVersionPanel({ hideTitle = false }: { hideTitle?: boolean } = {}) {
  const [current, setCurrent] = useState<AppVersionInfo | null>(null);
  const [fields, setFields] = useState<Fields>(EMPTY_APP_VERSION_FORM);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const session = loadStoredSession();
    if (!session?.accessToken) {
      return;
    }
    let active = true;
    fetchAppVersionConfig(session.accessToken)
      .then((info) => {
        if (active) {
          setCurrent(info);
          setFields(appVersionFormFrom(info));
        }
      })
      .catch((cause) => {
        if (active) {
          setError(getApiErrorMessage(cause, "Impossibile leggere la versione dell'app."));
        }
      });
    return () => {
      active = false;
    };
  }, []);

  function update(key: keyof Fields, value: string) {
    setFields((previous) => ({ ...previous, [key]: value }));
    setErrors((previous) => ({ ...previous, [key]: undefined }));
  }

  async function save() {
    setMessage(null);
    setError(null);
    const found = validateAppVersionForm(fields);
    setErrors(found);
    if (Object.keys(found).length > 0) {
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setBusy(true);
    try {
      const saved = await saveAppVersionConfig(session.accessToken, appVersionUpdateFrom(fields));
      setCurrent(saved);
      setFields(appVersionFormFrom(saved));
      setMessage("Versione salvata: chi ha un'app più vecchia vedrà l'avviso.");
    } catch (cause) {
      setError(getApiErrorMessage(cause, "Salvataggio non riuscito."));
    } finally {
      setBusy(false);
    }
  }

  const android = current?.android ?? null;

  return (
    <section
      className="fa-admin-appversion"
      aria-labelledby="admin-appversion-title"
      data-testid="admin-appversion"
    >
      <h2 id="admin-appversion-title" className={hideTitle ? "fa-sr-only" : undefined}>
        Versione dell'app Android
      </h2>
      <p className="fa-admin-appversion__hint">
        Quando pubblichi un nuovo APK, aggiorna qui versione e link: chi ha un'app più vecchia
        vedrà l'avviso.
      </p>
      {current ? (
        <p data-testid="admin-appversion-current">
          {android
            ? `Ora annunciata: ${android.latestVersionName} (versionCode ${android.latestVersionCode}).`
            : "Nessuna versione impostata: nell'app non compare nessun avviso."}
        </p>
      ) : null}
      <form
        className="fa-admin-appversion__form"
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <Input
          label="Versione (es. 1.3.0)"
          name="app-version-name"
          inputMode="decimal"
          autoComplete="off"
          value={fields.name}
          error={errors.name}
          onChange={(event) => update("name", event.target.value)}
        />
        <Input
          label="versionCode Android"
          name="app-version-code"
          type="number"
          inputMode="numeric"
          min={1}
          step={1}
          value={fields.code}
          error={errors.code}
          onChange={(event) => update("code", event.target.value)}
        />
        <Input
          label="Link di download (https)"
          name="app-version-url"
          type="url"
          autoComplete="off"
          value={fields.url}
          error={errors.url}
          onChange={(event) => update("url", event.target.value)}
        />
        <Input
          label="Messaggio breve (facoltativo)"
          name="app-version-message"
          maxLength={200}
          value={fields.message}
          error={errors.message}
          onChange={(event) => update("message", event.target.value)}
        />
        <div className="fa-admin-appversion__actions">
          <Button type="submit" variant="primary" loading={busy} data-testid="admin-appversion-save">
            Salva
          </Button>
        </div>
      </form>
      {message ? <p role="status">{message}</p> : null}
      {error ? (
        <p role="alert" className="fa-field__error">
          {error}
        </p>
      ) : null}
    </section>
  );
}
