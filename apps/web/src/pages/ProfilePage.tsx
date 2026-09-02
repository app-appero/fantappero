import {
  DELETE_ACCOUNT_CONFIRMATION_PHRASE,
  PROFILE_LANGUAGE_OPTIONS,
  PROFILE_TIMEZONE_OPTIONS,
  type UserProfile,
} from "@fantappero/contracts";
import {
  Breadcrumb,
  Button,
  Card,
  CardBody,
  CardHeader,
  Input,
  PageContainer,
  Select,
  UiStatePanel,
} from "@fantappero/ui";
import { type ChangeEvent, type FormEvent, useCallback, useEffect, useState } from "react";
import {
  fetchProfile,
  recordPolicyConsent,
  removeAvatar,
  updateInviteAvailability,
  updateProfile,
  uploadAvatar,
} from "../api/profile";
import { deleteAccount, exportAccountData } from "../api/privacy";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { resolveAvatarUrl } from "../utils/avatar";

const DEMO_PROFILE: UserProfile = {
  email: "demo@fantappero.local",
  displayName: "Marco Rossi",
  avatarUrl: null,
  language: "it",
  timezone: "Europe/Rome",
  notificationsEmail: true,
  notificationsPush: true,
  quietHoursStartHour: null,
  quietHoursEndHour: null,
  policyConsentAt: "2026-01-15T10:00:00.000Z",
  policyVersion: "2026-01",
  currentPolicyVersion: "2026-01",
  userType: "human",
  availableForInvites: true,
};

function profileInviteAvailability(profile: UserProfile): boolean {
  return profile.availableForInvites;
}

/** Profilo utente — preferenze, avatar e consenso policy (EP02-02). */
export function ProfilePage() {
  const { isDemoMode, user, updateDisplayName, logout } = useAuth();

  const demoProfile = isDemoMode
    ? { ...DEMO_PROFILE, displayName: user?.displayName ?? DEMO_PROFILE.displayName }
    : null;

  const [profile, setProfile] = useState<UserProfile | null>(() => demoProfile);
  const [loading, setLoading] = useState(!isDemoMode);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [avatarUploading, setAvatarUploading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [savingInviteAvailability, setSavingInviteAvailability] = useState(false);
  const [availableForInvites, setAvailableForInvites] = useState(
    demoProfile ? profileInviteAvailability(demoProfile) : true,
  );
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteConfirmPhrase, setDeleteConfirmPhrase] = useState("");
  const [privacyError, setPrivacyError] = useState<string | null>(null);
  const [privacySuccess, setPrivacySuccess] = useState<string | null>(null);

  const [displayName, setDisplayName] = useState(demoProfile?.displayName ?? "");
  const [language, setLanguage] = useState(demoProfile?.language ?? "it");
  const [timezone, setTimezone] = useState(demoProfile?.timezone ?? "Europe/Rome");
  const [notificationsEmail, setNotificationsEmail] = useState(
    demoProfile?.notificationsEmail ?? true,
  );
  const [notificationsPush, setNotificationsPush] = useState(
    demoProfile?.notificationsPush ?? true,
  );
  const [quietHoursStartHour, setQuietHoursStartHour] = useState<string>(
    demoProfile?.quietHoursStartHour?.toString() ?? "",
  );
  const [quietHoursEndHour, setQuietHoursEndHour] = useState<string>(
    demoProfile?.quietHoursEndHour?.toString() ?? "",
  );
  const [policyAccepted, setPolicyAccepted] = useState(
    demoProfile ? demoProfile.policyVersion === demoProfile.currentPolicyVersion : false,
  );

  const applyProfile = useCallback((next: UserProfile) => {
    setProfile(next);
    setDisplayName(next.displayName);
    setLanguage(next.language);
    setTimezone(next.timezone);
    setNotificationsEmail(next.notificationsEmail);
    setNotificationsPush(next.notificationsPush);
    setQuietHoursStartHour(next.quietHoursStartHour?.toString() ?? "");
    setQuietHoursEndHour(next.quietHoursEndHour?.toString() ?? "");
    setAvailableForInvites(profileInviteAvailability(next));
    setPolicyAccepted(next.policyVersion === next.currentPolicyVersion);
  }, []);

  useEffect(() => {
    if (isDemoMode) {
      if (demoProfile) {
        applyProfile(demoProfile);
      }
      setLoading(false);
      return;
    }

    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setLoadError("Sessione non disponibile. Accedi di nuovo.");
      setLoading(false);
      return;
    }

    let cancelled = false;
    fetchProfile(stored.accessToken)
      .then((loaded) => {
        if (!cancelled) {
          applyProfile(loaded);
          setLoadError(null);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setLoadError(getApiErrorMessage(error, "Impossibile caricare il profilo."));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [applyProfile, demoProfile, isDemoMode, user?.displayName]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setSuccessMessage(null);

    if (isDemoMode) {
      setSuccessMessage("Modalità demo: le modifiche non vengono salvate.");
      return;
    }

    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setFormError("Sessione scaduta. Accedi di nuovo.");
      return;
    }

    if (
      (quietHoursStartHour.trim() === "") !== (quietHoursEndHour.trim() === "")
    ) {
      setFormError("Imposta sia l'inizio sia la fine del silenzio, oppure lasciali entrambi vuoti.");
      return;
    }

    setSaving(true);
    try {
      const updated = await updateProfile(stored.accessToken, {
        displayName,
        language,
        timezone,
        notificationsEmail,
        notificationsPush,
        quietHoursStartHour: quietHoursStartHour.trim() === "" ? null : Number(quietHoursStartHour),
        quietHoursEndHour: quietHoursEndHour.trim() === "" ? null : Number(quietHoursEndHour),
      });
      applyProfile(updated);
      updateDisplayName(updated.displayName);
      setSuccessMessage("Preferenze salvate con successo.");
    } catch (submitError) {
      setFormError(getApiErrorMessage(submitError, "Salvataggio non riuscito."));
    } finally {
      setSaving(false);
    }
  }

  async function handleAvatarChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || isDemoMode) {
      return;
    }

    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setFormError("Sessione scaduta. Accedi di nuovo.");
      return;
    }

    setAvatarUploading(true);
    setFormError(null);
    setSuccessMessage(null);
    try {
      const updated = await uploadAvatar(stored.accessToken, file);
      applyProfile(updated);
      setSuccessMessage("Avatar aggiornato.");
    } catch (uploadError) {
      setFormError(getApiErrorMessage(uploadError, "Caricamento avatar non riuscito."));
    } finally {
      setAvatarUploading(false);
    }
  }

  async function handleRemoveAvatar() {
    if (isDemoMode || !profile?.avatarUrl) {
      return;
    }

    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setFormError("Sessione scaduta. Accedi di nuovo.");
      return;
    }

    setAvatarUploading(true);
    setFormError(null);
    try {
      const updated = await removeAvatar(stored.accessToken);
      applyProfile(updated);
      setSuccessMessage("Avatar rimosso.");
    } catch (removeError) {
      setFormError(getApiErrorMessage(removeError, "Rimozione avatar non riuscita."));
    } finally {
      setAvatarUploading(false);
    }
  }

  async function handlePolicyConsent() {
    if (isDemoMode) {
      setSuccessMessage("Modalità demo: consenso simulato.");
      setPolicyAccepted(true);
      return;
    }

    const stored = loadStoredSession();
    if (!stored?.accessToken || !profile) {
      setFormError("Sessione scaduta. Accedi di nuovo.");
      return;
    }

    setSaving(true);
    setFormError(null);
    try {
      const updated = await recordPolicyConsent(stored.accessToken, {
        policyVersion: profile.currentPolicyVersion,
        accepted: true,
      });
      applyProfile(updated);
      setPolicyAccepted(true);
      setSuccessMessage("Consenso alla policy registrato.");
    } catch (consentError) {
      setFormError(getApiErrorMessage(consentError, "Registrazione consenso non riuscita."));
    } finally {
      setSaving(false);
    }
  }

  async function handleInviteAvailabilityChange(next: boolean) {
    setFormError(null);
    setSuccessMessage(null);
    if (profile?.userType === "ai") {
      setFormError("Gli account IA sono sempre disponibili e non possono modificare questa preferenza.");
      return;
    }
    if (isDemoMode) {
      setAvailableForInvites(next);
      setSuccessMessage("Disponibilità agli inviti aggiornata (demo).");
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setFormError("Sessione scaduta. Accedi di nuovo.");
      return;
    }
    setSavingInviteAvailability(true);
    try {
      const updated = await updateInviteAvailability(stored.accessToken, next);
      applyProfile(updated);
      setSuccessMessage("Disponibilità agli inviti aggiornata.");
    } catch (availabilityError) {
      setFormError(
        getApiErrorMessage(availabilityError, "Aggiornamento disponibilità non riuscito."),
      );
    } finally {
      setSavingInviteAvailability(false);
    }
  }

  async function handleExportData() {
    setPrivacyError(null);
    setPrivacySuccess(null);

    if (isDemoMode) {
      setPrivacySuccess("Modalità demo: esportazione simulata.");
      return;
    }

    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setPrivacyError("Sessione scaduta. Accedi di nuovo.");
      return;
    }

    setExporting(true);
    try {
      const payload = await exportAccountData(stored.accessToken);
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json;charset=utf-8",
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `fantappero-export-${payload.exportedAt.slice(0, 10)}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
      setPrivacySuccess("Esportazione completata. Il file JSON è stato scaricato.");
    } catch (exportError) {
      setPrivacyError(getApiErrorMessage(exportError, "Esportazione non riuscita."));
    } finally {
      setExporting(false);
    }
  }

  async function handleDeleteAccount() {
    setPrivacyError(null);
    setPrivacySuccess(null);

    if (isDemoMode) {
      setPrivacySuccess("Modalità demo: eliminazione simulata.");
      return;
    }

    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setPrivacyError("Sessione scaduta. Accedi di nuovo.");
      return;
    }

    if (deleteConfirmPhrase.trim() !== DELETE_ACCOUNT_CONFIRMATION_PHRASE) {
      setPrivacyError(`Digita "${DELETE_ACCOUNT_CONFIRMATION_PHRASE}" per confermare.`);
      return;
    }

    setDeleting(true);
    try {
      const result = await deleteAccount(stored.accessToken, {
        password: deletePassword,
        confirmPhrase: deleteConfirmPhrase.trim(),
      });
      setPrivacySuccess(result.message);
      setDeletePassword("");
      setDeleteConfirmPhrase("");
      await logout();
    } catch (deleteError) {
      setPrivacyError(getApiErrorMessage(deleteError, "Eliminazione account non riuscita."));
    } finally {
      setDeleting(false);
    }
  }

  if (loading) {
    return (
      <PageContainer title="Profilo" header={<Breadcrumb items={[{ label: "Profilo" }]} />}>
        <UiStatePanel
          state="loading"
          title="Caricamento profilo"
          message="Stiamo recuperando le tue preferenze…"
          testId="profile-loading"
        />
      </PageContainer>
    );
  }

  if (loadError) {
    return (
      <PageContainer title="Profilo" header={<Breadcrumb items={[{ label: "Profilo" }]} />}>
        <UiStatePanel
          state="error"
          title="Profilo non disponibile"
          message={loadError}
          testId="profile-error"
        />
      </PageContainer>
    );
  }

  if (!profile) {
    return (
      <PageContainer title="Profilo" header={<Breadcrumb items={[{ label: "Profilo" }]} />}>
        <UiStatePanel
          state="empty"
          title="Nessun profilo"
          message="Non abbiamo trovato dati profilo per il tuo account."
          testId="profile-empty"
        />
      </PageContainer>
    );
  }

  const avatarSrc = resolveAvatarUrl(profile.avatarUrl);
  const needsPolicyConsent = profile.policyVersion !== profile.currentPolicyVersion;

  return (
    <PageContainer title="Profilo" header={<Breadcrumb items={[{ label: "Profilo" }]} />}>
      {successMessage ? (
        <UiStatePanel
          state="success"
          title="Operazione completata"
          message={successMessage}
          testId="profile-success"
        />
      ) : null}

      <div className="fa-profile-grid">
        <Card>
          <CardHeader title="Identità" />
          <CardBody>
            <div className="fa-profile-avatar">
              {avatarSrc ? (
                <img
                  src={avatarSrc}
                  alt=""
                  className="fa-profile-avatar__image"
                  data-testid="profile-avatar-image"
                />
              ) : (
                <div className="fa-profile-avatar__placeholder" data-testid="profile-avatar-placeholder">
                  {profile.displayName.charAt(0).toUpperCase()}
                </div>
              )}
              <div className="fa-profile-avatar__actions">
                <label className="fa-button fa-button--secondary fa-button--sm">
                  {avatarUploading ? "Caricamento…" : "Carica avatar"}
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    hidden
                    disabled={avatarUploading || isDemoMode}
                    onChange={handleAvatarChange}
                    data-testid="profile-avatar-input"
                  />
                </label>
                {profile.avatarUrl ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={avatarUploading || isDemoMode}
                    onClick={() => void handleRemoveAvatar()}
                    data-testid="profile-avatar-remove"
                  >
                    Rimuovi
                  </Button>
                ) : null}
              </div>
            </div>
            <p className="fa-field__hint">JPEG, PNG o WebP — massimo 2 MB.</p>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Preferenze" />
          <CardBody>
            <form className="fa-profile-form" onSubmit={handleSubmit} data-testid="profile-form">
              <Input
                label="Nome visualizzato"
                name="displayName"
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                required
                disabled={saving}
              />
              <Input
                label="Email"
                name="email"
                value={profile.email}
                readOnly
                disabled
                hint="L'email non è modificabile da questa schermata."
              />
              <Select
                label="Lingua"
                name="language"
                value={language}
                options={[...PROFILE_LANGUAGE_OPTIONS]}
                onChange={(event) => setLanguage(event.target.value)}
                disabled={saving}
              />
              <Select
                label="Fuso orario"
                name="timezone"
                value={timezone}
                options={[...PROFILE_TIMEZONE_OPTIONS]}
                onChange={(event) => setTimezone(event.target.value)}
                disabled={saving}
              />
              <fieldset className="fa-profile-notifications">
                <legend className="fa-field__label">Notifiche</legend>
                <label className="fa-profile-checkbox">
                  <input
                    type="checkbox"
                    checked={notificationsEmail}
                    onChange={(event) => setNotificationsEmail(event.target.checked)}
                    disabled={saving}
                    data-testid="profile-notifications-email"
                  />
                  Email
                </label>
                <label className="fa-profile-checkbox">
                  <input
                    type="checkbox"
                    checked={notificationsPush}
                    onChange={(event) => setNotificationsPush(event.target.checked)}
                    disabled={saving}
                    data-testid="profile-notifications-push"
                  />
                  Push
                </label>
              </fieldset>

              <fieldset className="fa-profile-notifications">
                <legend className="fa-field__label">Silenzio notifiche (email/push)</legend>
                <Input
                  label="Dalle ore"
                  name="quietHoursStartHour"
                  type="number"
                  min={0}
                  max={23}
                  value={quietHoursStartHour}
                  onChange={(event) => setQuietHoursStartHour(event.target.value)}
                  disabled={saving}
                  data-testid="profile-quiet-hours-start"
                />
                <Input
                  label="Alle ore"
                  name="quietHoursEndHour"
                  type="number"
                  min={0}
                  max={23}
                  value={quietHoursEndHour}
                  onChange={(event) => setQuietHoursEndHour(event.target.value)}
                  disabled={saving}
                  data-testid="profile-quiet-hours-end"
                />
              </fieldset>

              <fieldset className="fa-profile-notifications">
                <legend className="fa-field__label">Inviti nominativi</legend>
                <label className="fa-profile-checkbox">
                  <input
                    type="checkbox"
                    checked={availableForInvites}
                    onChange={(event) => void handleInviteAvailabilityChange(event.target.checked)}
                    disabled={
                      savingInviteAvailability || profile?.userType === "ai"
                    }
                    data-testid="profile-invite-availability"
                  />
                  Disponibile a ricevere inviti alle leghe
                </label>
                <p className="fa-field__hint">
                  {profile?.userType === "ai"
                    ? "Gli account IA sono sempre disponibili e non possono modificare questa preferenza."
                    : "Se disattivato, risulterai non disponibile nella directory e non potrai essere invitato."}
                </p>
              </fieldset>

              {formError ? (
                <p className="fa-field__error" role="alert" data-testid="profile-form-error">
                  {formError}
                </p>
              ) : null}

              <Button type="submit" disabled={saving} data-testid="profile-save">
                {saving ? "Salvataggio…" : "Salva preferenze"}
              </Button>
            </form>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Privacy" />
          <CardBody>
            {privacySuccess ? (
              <UiStatePanel
                state="success"
                title="Operazione privacy completata"
                message={privacySuccess}
                testId="profile-privacy-success"
              />
            ) : null}

            {privacyError ? (
              <UiStatePanel
                state="error"
                title="Operazione non riuscita"
                message={privacyError}
                testId="profile-privacy-error"
              />
            ) : null}

            {needsPolicyConsent ? (
              <div className="fa-profile-policy" data-testid="profile-policy-pending">
                <p>
                  È disponibile una nuova versione della policy ({profile.currentPolicyVersion}).
                  Accetta per continuare a usare FantApperò.
                </p>
                <label className="fa-profile-checkbox">
                  <input
                    type="checkbox"
                    checked={policyAccepted}
                    onChange={(event) => setPolicyAccepted(event.target.checked)}
                    disabled={saving}
                    data-testid="profile-policy-checkbox"
                  />
                  Accetto la policy sulla privacy
                </label>
                <Button
                  type="button"
                  disabled={!policyAccepted || saving}
                  onClick={() => void handlePolicyConsent()}
                  data-testid="profile-policy-submit"
                >
                  Registra consenso
                </Button>
              </div>
            ) : (
              <UiStatePanel
                state="success"
                title="Policy accettata"
                message={`Consenso registrato il ${profile.policyConsentAt ? new Date(profile.policyConsentAt).toLocaleString("it-IT") : "—"} (versione ${profile.policyVersion}).`}
                testId="profile-policy-accepted"
              />
            )}

            <div className="fa-profile-privacy-actions" data-testid="profile-privacy-actions">
              <h3 className="fa-profile-privacy-actions__title">I tuoi dati</h3>
              <p className="fa-field__hint">
                Scarica una copia leggibile dei dati del tuo account. L&apos;operazione viene
                registrata per audit.
              </p>
              <Button
                type="button"
                variant="secondary"
                disabled={exporting || deleting || isDemoMode}
                onClick={() => void handleExportData()}
                data-testid="profile-export-data"
              >
                {exporting ? "Esportazione…" : "Esporta i miei dati"}
              </Button>

              <h3 className="fa-profile-privacy-actions__title fa-profile-privacy-actions__title--danger">
                Elimina account
              </h3>
              <p className="fa-field__hint">
                L&apos;eliminazione rimuove i dati personali e preserva gli storici di lega con un
                nome anonimo. L&apos;operazione è irreversibile.
              </p>
              <Input
                label="Password attuale"
                name="deletePassword"
                type="password"
                value={deletePassword}
                onChange={(event) => setDeletePassword(event.target.value)}
                disabled={deleting || isDemoMode}
                autoComplete="current-password"
              />
              <Input
                label={`Conferma digitando ${DELETE_ACCOUNT_CONFIRMATION_PHRASE}`}
                name="deleteConfirmPhrase"
                value={deleteConfirmPhrase}
                onChange={(event) => setDeleteConfirmPhrase(event.target.value)}
                disabled={deleting || isDemoMode}
              />
              <Button
                type="button"
                variant="ghost"
                disabled={
                  deleting ||
                  isDemoMode ||
                  !deletePassword ||
                  deleteConfirmPhrase.trim() !== DELETE_ACCOUNT_CONFIRMATION_PHRASE
                }
                onClick={() => void handleDeleteAccount()}
                data-testid="profile-delete-submit"
              >
                {deleting ? "Eliminazione…" : "Elimina il mio account"}
              </Button>
            </div>
          </CardBody>
        </Card>
      </div>
    </PageContainer>
  );
}

export function NotFoundPage() {
  return (
    <PageContainer title="Pagina non trovata">
      <UiStatePanel
        state="error"
        title="404"
        message="La pagina richiesta non esiste o è stata spostata."
        testId="not-found"
      />
    </PageContainer>
  );
}
