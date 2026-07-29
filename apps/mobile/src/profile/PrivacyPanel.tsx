import { useState } from "react";

import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import {

  DEFAULT_UI_LOCALE,

  type PrivacyFormState,

  type UserDataExportResponse,

  ui,

} from "@fantappero/contracts";

import { colors, spacing, typography } from "@fantappero/ui";

import { AuthApiError, type AuthClient } from "../api/auth";



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

      setExportState({

        status: "error",

        error:

          error instanceof AuthApiError

            ? { code: error.code, message: error.message }

            : { code: "network_error", message: copy.networkError },

      });

    }

  }



  async function handleDelete() {

    if (!password.trim() || !confirmDelete) {

      setDeleteState({ status: "empty" });

      return;

    }

    setDeleteState({ status: "loading" });

    try {

      const response = await client.deleteAccount(token, { password, confirm: true });

      setDeleteState({ status: "success", message: response.message });

      onDeleted();

    } catch (error) {

      setDeleteState({

        status: "error",

        error:

          error instanceof AuthApiError

            ? { code: error.code, message: error.message }

            : { code: "network_error", message: copy.networkError },

      });

    }

  }



  return (

    <View testID="privacy-panel">

      <Text style={styles.title}>{copy.yourData}</Text>

      <Text style={styles.muted}>{copy.privacyIntro}</Text>



      {exportState.status === "loading" ? (

        <ActivityIndicator color={colors.ok} testID="privacy-status" />

      ) : null}

      {exportState.status === "error" && exportState.error ? (

        <Text style={styles.error} testID="privacy-error">

          {exportState.error.message}

        </Text>

      ) : null}

      {exportState.status === "success" && exportState.message ? (

        <Text style={styles.success} testID="privacy-success">

          {exportState.message}

        </Text>

      ) : null}

      {exportState.status === "empty" ? (

        <Text style={styles.muted} testID="privacy-empty">

          {copy.deleteConfirmHint}

        </Text>

      ) : null}



      <Pressable style={styles.button} onPress={() => void handleExport()} testID="privacy-export">

        <Text style={styles.buttonLabel}>{copy.exportMyData}</Text>

      </Pressable>



      {exportPreview ? (

        <Text style={styles.preview} testID="privacy-export-preview" numberOfLines={8}>

          {JSON.stringify(exportPreview)}

        </Text>

      ) : (

        <Text style={styles.muted} testID="privacy-export-empty">

          {copy.noExportYet}

        </Text>

      )}



      <Text style={styles.title}>{copy.deleteAccount}</Text>

      <TextInput

        testID="privacy-delete-password"

        style={styles.input}

        secureTextEntry

        value={password}

        onChangeText={setPassword}

        placeholder={copy.password}

        placeholderTextColor={colors.muted}

      />

      <Pressable

        style={styles.checkboxRow}

        onPress={() => setConfirmDelete((value) => !value)}

        testID="privacy-delete-confirm"

      >

        <Text style={styles.muted}>

          {confirmDelete ? "[x]" : "[ ]"} {copy.deleteConfirmCheckbox}

        </Text>

      </Pressable>

      <Pressable style={styles.dangerButton} onPress={() => void handleDelete()} testID="privacy-delete-submit">

        <Text style={styles.buttonLabel}>{copy.deleteMyAccount}</Text>

      </Pressable>

    </View>

  );

}



const styles = StyleSheet.create({

  title: {

    marginTop: spacing.md,

    fontSize: typography.fontSize.lg,

    fontWeight: "600",

    color: colors.foreground,

  },

  muted: {

    color: colors.muted,

    marginTop: spacing.xs,

  },

  error: {

    color: "#f87171",

    marginTop: spacing.sm,

  },

  success: {

    color: colors.ok,

    marginTop: spacing.sm,

  },

  button: {

    marginTop: spacing.sm,

    backgroundColor: colors.ok,

    padding: spacing.sm,

    borderRadius: 8,

  },

  dangerButton: {

    marginTop: spacing.sm,

    backgroundColor: "#dc2626",

    padding: spacing.sm,

    borderRadius: 8,

  },

  buttonLabel: {

    color: colors.background,

    fontWeight: "600",

    textAlign: "center",

  },

  input: {

    marginTop: spacing.sm,

    borderWidth: 1,

    borderColor: colors.muted,

    borderRadius: 8,

    padding: spacing.sm,

    color: colors.foreground,

  },

  checkboxRow: {

    marginTop: spacing.sm,

  },

  preview: {

    marginTop: spacing.sm,

    fontSize: typography.fontSize.sm,

    color: colors.foreground,

  },

});


