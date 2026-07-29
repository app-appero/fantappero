import { useEffect, useState, type ChangeEvent, type CSSProperties, type FormEvent, type ReactNode } from "react";

import {

  LANGUAGE_LABELS,

  PROFILE_POLICY_VERSION,

  SUPPORTED_LANGUAGES,

  type ProfileFormState,

  type SupportedLanguage,

  type UserProfileResponse,

  ui,

} from "@fantappero/contracts";

import { colors, spacing, typography } from "@fantappero/ui";

import { AuthApiError, type AuthClient } from "../api/auth";



const initialFormState: ProfileFormState = { status: "idle" };



function resolveLocale(language: string): SupportedLanguage {

  if (SUPPORTED_LANGUAGES.includes(language as SupportedLanguage)) {

    return language as SupportedLanguage;

  }

  return "it";

}



function fieldStyle(): CSSProperties {

  return {

    width: "100%",

    padding: spacing.sm,

    borderRadius: 8,

    border: `1px solid ${colors.muted}`,

    background: colors.background,

    color: colors.foreground,

    fontFamily: typography.fontFamily,

    fontSize: typography.fontSize.md,

    boxSizing: "border-box",

  };

}



function buttonStyle(disabled: boolean): CSSProperties {

  return {

    marginTop: spacing.sm,

    padding: `${spacing.sm}px ${spacing.md}px`,

    borderRadius: 8,

    border: "none",

    background: disabled ? colors.muted : colors.ok,

    color: colors.background,

    fontWeight: 600,

    cursor: disabled ? "not-allowed" : "pointer",

    fontFamily: typography.fontFamily,

  };

}



function statusBanner(state: ProfileFormState, copy: ReturnType<typeof ui>): ReactNode {

  if (state.status === "loading") {

    return (

      <p data-testid="profile-status" style={{ color: colors.muted }}>

        {copy.saving}

      </p>

    );

  }

  if (state.status === "error" && state.error) {

    return (

      <p data-testid="profile-error" style={{ color: "#f87171" }}>

        {state.error.message}

      </p>

    );

  }

  if (state.status === "success" && state.message) {

    return (

      <p data-testid="profile-success" style={{ color: colors.ok }}>

        {state.message}

      </p>

    );

  }

  if (state.status === "empty") {

    return (

      <p data-testid="profile-empty" style={{ color: colors.muted }}>

        {copy.profileEmptyChange}

      </p>

    );

  }

  return null;

}



export interface ProfilePanelProps {

  client: AuthClient;

  token: string;

  profile: UserProfileResponse;

  onUpdated: (profile: UserProfileResponse) => void;

}



export function ProfilePanel({ client, token, profile, onUpdated }: ProfilePanelProps) {

  const copy = ui(resolveLocale(profile.language));

  const [form, setForm] = useState(initialFormState);

  const [displayName, setDisplayName] = useState(profile.display_name ?? "");

  const [language, setLanguage] = useState(profile.language);

  const [timezone, setTimezone] = useState(profile.timezone);

  const [notificationsEmail, setNotificationsEmail] = useState(profile.notifications.email);

  const [notificationsPush, setNotificationsPush] = useState(profile.notifications.push);

  const [acceptPolicy, setAcceptPolicy] = useState(false);



  useEffect(() => {

    setDisplayName(profile.display_name ?? "");

    setLanguage(profile.language);

    setTimezone(profile.timezone);

    setNotificationsEmail(profile.notifications.email);

    setNotificationsPush(profile.notifications.push);

  }, [profile]);



  async function handleSave(event: FormEvent) {

    event.preventDefault();



    const payload: Record<string, unknown> = {};

    const trimmedName = displayName.trim();

    if (trimmedName !== (profile.display_name ?? "")) {

      if (!trimmedName) {

        setForm({ status: "empty" });

        return;

      }

      payload.display_name = trimmedName;

    }

    if (language !== profile.language) {

      payload.language = language;

    }

    if (timezone.trim() !== profile.timezone) {

      if (!timezone.trim()) {

        setForm({ status: "empty" });

        return;

      }

      payload.timezone = timezone.trim();

    }

    if (notificationsEmail !== profile.notifications.email) {

      payload.notifications_email = notificationsEmail;

    }

    if (notificationsPush !== profile.notifications.push) {

      payload.notifications_push = notificationsPush;

    }

    if (acceptPolicy && !profile.policy_consent_at) {

      payload.accept_policy = true;

      payload.policy_version = PROFILE_POLICY_VERSION;

    }



    if (Object.keys(payload).length === 0) {

      setForm({ status: "empty" });

      return;

    }



    setForm({ status: "loading" });

    try {

      const updated = await client.updateProfile(token, payload);

      onUpdated(updated);

      setAcceptPolicy(false);

      setForm({ status: "success", message: copy.profileSaved });

    } catch (error) {

      if (error instanceof AuthApiError) {

        setForm({ status: "error", error: { code: error.code, message: error.message } });

      } else {

        setForm({

          status: "error",

          error: { code: "network_error", message: copy.networkError },

        });

      }

    }

  }



  async function handleAvatarChange(event: ChangeEvent<HTMLInputElement>) {

    const file = event.target.files?.[0];

    if (!file) {

      return;

    }

    setForm({ status: "loading" });

    try {

      const updated = await client.uploadAvatar(token, file);

      onUpdated(updated);

      setForm({ status: "success", message: copy.avatarUpdated });

    } catch (error) {

      if (error instanceof AuthApiError) {

        setForm({ status: "error", error: { code: error.code, message: error.message } });

      } else {

        setForm({

          status: "error",

          error: { code: "network_error", message: copy.unableUploadAvatar },

        });

      }

    } finally {

      event.target.value = "";

    }

  }



  return (

    <section data-testid="profile-panel">

      {statusBanner(form, copy)}



      {profile.avatar_url ? (

        <img

          data-testid="profile-avatar"

          src={profile.avatar_url}

          alt={copy.avatar}

          style={{ width: 64, height: 64, borderRadius: "50%", marginBottom: spacing.sm }}

        />

      ) : (

        <p data-testid="profile-avatar-empty" style={{ color: colors.muted }}>

          {copy.noAvatar}

        </p>

      )}



      <label style={{ display: "block", marginBottom: spacing.sm }}>

        {copy.avatar}

        <input

          data-testid="profile-avatar-input"

          type="file"

          accept="image/png,image/jpeg,image/webp"

          onChange={(event) => void handleAvatarChange(event)}

          style={fieldStyle()}

        />

      </label>



      <form onSubmit={(event) => void handleSave(event)} style={{ maxWidth: 420 }}>

        <label style={{ display: "block", marginBottom: spacing.sm }}>

          {copy.displayName}

          <input

            data-testid="profile-display-name"

            value={displayName}

            onChange={(event) => setDisplayName(event.target.value)}

            style={fieldStyle()}

          />

        </label>



        <label style={{ display: "block", marginBottom: spacing.sm }}>

          {copy.language}

          <select

            data-testid="profile-language"

            value={language}

            onChange={(event) => setLanguage(event.target.value)}

            style={fieldStyle()}

          >

            {SUPPORTED_LANGUAGES.map((code) => (

              <option key={code} value={code}>

                {LANGUAGE_LABELS[code]}

              </option>

            ))}

          </select>

        </label>



        <label style={{ display: "block", marginBottom: spacing.sm }}>

          {copy.timezone}

          <input

            data-testid="profile-timezone"

            value={timezone}

            onChange={(event) => setTimezone(event.target.value)}

            style={fieldStyle()}

          />

        </label>



        <label style={{ display: "block", marginBottom: spacing.sm }}>

          <input

            data-testid="profile-notifications-email"

            type="checkbox"

            checked={notificationsEmail}

            onChange={(event) => setNotificationsEmail(event.target.checked)}

          />{" "}

          {copy.emailNotifications}

        </label>



        <label style={{ display: "block", marginBottom: spacing.sm }}>

          <input

            data-testid="profile-notifications-push"

            type="checkbox"

            checked={notificationsPush}

            onChange={(event) => setNotificationsPush(event.target.checked)}

          />{" "}

          {copy.pushNotifications}

        </label>



        {profile.policy_consent_at ? (

          <p data-testid="profile-policy-accepted" style={{ color: colors.muted }}>

            {copy.policyAccepted} ({profile.policy_version}) —{" "}

            {new Date(profile.policy_consent_at).toLocaleDateString("it-IT")}

          </p>

        ) : (

          <label style={{ display: "block", marginBottom: spacing.sm }}>

            <input

              data-testid="profile-accept-policy"

              type="checkbox"

              checked={acceptPolicy}

              onChange={(event) => setAcceptPolicy(event.target.checked)}

            />{" "}

            {copy.acceptPolicy}

            {PROFILE_POLICY_VERSION}

          </label>

        )}



        <button

          data-testid="profile-save"

          type="submit"

          style={buttonStyle(form.status === "loading")}

          disabled={form.status === "loading"}

        >

          {copy.saveProfile}

        </button>

      </form>

    </section>

  );

}


