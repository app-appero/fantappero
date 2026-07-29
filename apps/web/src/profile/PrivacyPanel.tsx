import { useState, type CSSProperties, type FormEvent, type ReactNode } from "react";

import {

  DEFAULT_UI_LOCALE,

  type PrivacyFormState,

  type UserDataExportResponse,

  ui,

} from "@fantappero/contracts";

import { colors, spacing, typography } from "@fantappero/ui";

import { AuthApiError, type AuthClient } from "../api/auth";



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



function buttonStyle(disabled: boolean, danger = false): CSSProperties {

  return {

    marginTop: spacing.sm,

    padding: `${spacing.sm}px ${spacing.md}px`,

    borderRadius: 8,

    border: "none",

    background: disabled ? colors.muted : danger ? "#dc2626" : colors.ok,

    color: colors.background,

    fontWeight: 600,

    cursor: disabled ? "not-allowed" : "pointer",

    fontFamily: typography.fontFamily,

  };

}



function statusBanner(state: PrivacyFormState, copy: ReturnType<typeof ui>): ReactNode {

  if (state.status === "loading") {

    return (

      <p data-testid="privacy-status" style={{ color: colors.muted }}>

        {copy.working}

      </p>

    );

  }

  if (state.status === "error" && state.error) {

    return (

      <p data-testid="privacy-error" style={{ color: "#f87171" }}>

        {state.error.message}

      </p>

    );

  }

  if (state.status === "success" && state.message) {

    return (

      <p data-testid="privacy-success" style={{ color: colors.ok }}>

        {state.message}

      </p>

    );

  }

  if (state.status === "empty") {

    return (

      <p data-testid="privacy-empty" style={{ color: colors.muted }}>

        {copy.deleteConfirmHint}

      </p>

    );

  }

  return null;

}



export interface PrivacyPanelProps {

  client: AuthClient;

  token: string;

  onDeleted: () => void;

}



export function PrivacyPanel({ client, token, onDeleted }: PrivacyPanelProps) {

  const copy = ui(DEFAULT_UI_LOCALE);

  const [exportState, setExportState] = useState<PrivacyFormState>({ status: "idle" });

  const [deleteState, setDeleteState] = useState<PrivacyFormState>({ status: "idle" });

  const [exportPreview, setExportPreview] = useState<UserDataExportResponse | null>(null);

  const [password, setPassword] = useState("");

  const [confirmDelete, setConfirmDelete] = useState(false);



  async function handleExport() {

    setExportState({ status: "loading" });

    setExportPreview(null);

    try {

      const data = await client.exportData(token);

      setExportPreview(data);

      setExportState({

        status: "success",

        message: copy.exportReady(data.league_memberships.length),

      });

    } catch (error) {

      if (error instanceof AuthApiError) {

        setExportState({ status: "error", error: { code: error.code, message: error.message } });

      } else {

        setExportState({

          status: "error",

          error: { code: "network_error", message: copy.networkError },

        });

      }

    }

  }



  async function handleDelete(event: FormEvent) {

    event.preventDefault();

    if (!password.trim() || !confirmDelete) {

      setDeleteState({ status: "empty" });

      return;

    }

    setDeleteState({ status: "loading" });

    try {

      const response = await client.deleteAccount(token, {

        password,

        confirm: true,

      });

      setDeleteState({ status: "success", message: response.message });

      onDeleted();

    } catch (error) {

      if (error instanceof AuthApiError) {

        setDeleteState({ status: "error", error: { code: error.code, message: error.message } });

      } else {

        setDeleteState({

          status: "error",

          error: { code: "network_error", message: copy.networkError },

        });

      }

    }

  }



  return (

    <section data-testid="privacy-panel" style={{ maxWidth: 520 }}>

      <h2 style={{ fontSize: typography.fontSize.lg, marginTop: spacing.md }}>{copy.yourData}</h2>

      <p style={{ color: colors.muted }}>{copy.privacyIntro}</p>



      {statusBanner(exportState, copy)}

      <button

        type="button"

        style={buttonStyle(exportState.status === "loading")}

        data-testid="privacy-export"

        disabled={exportState.status === "loading"}

        onClick={() => void handleExport()}

      >

        {copy.exportMyData}

      </button>



      {exportPreview ? (

        <pre

          data-testid="privacy-export-preview"

          style={{

            marginTop: spacing.md,

            padding: spacing.sm,

            background: "#0f172a",

            borderRadius: 8,

            overflow: "auto",

            fontSize: typography.fontSize.sm,

            maxHeight: 240,

          }}

        >

          {JSON.stringify(exportPreview, null, 2)}

        </pre>

      ) : exportState.status === "success" ? null : (

        <p data-testid="privacy-export-empty" style={{ color: colors.muted, marginTop: spacing.sm }}>

          {copy.noExportYet}

        </p>

      )}



      <h2 style={{ fontSize: typography.fontSize.lg, marginTop: spacing.lg }}>{copy.deleteAccount}</h2>

      {statusBanner(deleteState, copy)}

      <form onSubmit={(event) => void handleDelete(event)}>

        <label style={{ display: "block", marginBottom: spacing.sm }}>

          {copy.password}

          <input

            data-testid="privacy-delete-password"

            type="password"

            value={password}

            onChange={(event) => setPassword(event.target.value)}

            style={fieldStyle()}

          />

        </label>

        <label style={{ display: "flex", gap: spacing.sm, alignItems: "center" }}>

          <input

            data-testid="privacy-delete-confirm"

            type="checkbox"

            checked={confirmDelete}

            onChange={(event) => setConfirmDelete(event.target.checked)}

          />

          {copy.deleteConfirmCheckbox}

        </label>

        <button

          type="submit"

          style={buttonStyle(deleteState.status === "loading", true)}

          data-testid="privacy-delete-submit"

          disabled={deleteState.status === "loading"}

        >

          {copy.deleteMyAccount}

        </button>

      </form>

    </section>

  );

}


