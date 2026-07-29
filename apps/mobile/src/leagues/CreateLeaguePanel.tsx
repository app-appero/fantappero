import { useEffect, useState } from "react";

import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import {
  MIN_LEAGUE_COMPETITIONS,
  type CompetitionResponse,
  type LeagueFormState,
  type LeagueResponse,
  type SupportedLanguage,
  ui,
} from "@fantappero/contracts";
import { colors, spacing, typography } from "@fantappero/ui";

import { AuthApiError } from "../api/auth";
import { mapApiErrorMessage } from "../api/errors";
import type { LeagueClient } from "../api/leagues";

const initialFormState: LeagueFormState = { status: "idle" };

export interface CreateLeaguePanelProps {
  client: LeagueClient;
  token: string;
  locale: SupportedLanguage;
  emailVerified: boolean;
  onVerifyEmail?: () => void;
  onCreated: (league: LeagueResponse) => void;
}

export function CreateLeaguePanel({
  client,
  token,
  locale,
  emailVerified,
  onVerifyEmail,
  onCreated,
}: CreateLeaguePanelProps) {
  const copy = ui(locale);
  const [form, setForm] = useState(initialFormState);
  const [name, setName] = useState("");
  const [seasonYear, setSeasonYear] = useState(String(new Date().getFullYear()));
  const [catalog, setCatalog] = useState<CompetitionResponse[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;
    setForm({ status: "loading" });
    void client
      .listCompetitions(token)
      .then((rows) => {
        if (!cancelled) {
          setCatalog(rows);
          setForm({ status: "idle" });
        }
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        if (error instanceof AuthApiError) {
          setForm({
            status: "error",
            error: {
              code: error.code,
              message: mapApiErrorMessage(copy, error.code, error.message),
            },
          });
        } else {
          setForm({
            status: "error",
            error: { code: "network_error", message: copy.networkError },
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [client, copy.networkError, token]);

  function toggleCompetition(id: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  async function handleSubmit() {
    if (!emailVerified) {
      setForm({
        status: "error",
        error: { code: "email_not_verified", message: copy.emailNotVerified },
      });
      return;
    }

    const trimmedName = name.trim();
    const parsedSeason = Number.parseInt(seasonYear, 10);
    if (!trimmedName || !Number.isFinite(parsedSeason) || selected.size < MIN_LEAGUE_COMPETITIONS) {
      setForm({ status: "empty" });
      return;
    }

    setForm({ status: "loading" });
    try {
      const league = await client.createLeague(token, {
        name: trimmedName,
        season_year: parsedSeason,
        competition_ids: [...selected],
      });
      onCreated(league);
      setForm({ status: "success", message: copy.leagueCreated });
    } catch (error) {
      if (error instanceof AuthApiError) {
        setForm({
          status: "error",
          error: {
            code: error.code,
            message: mapApiErrorMessage(copy, error.code, error.message),
          },
        });
      } else {
        setForm({
          status: "error",
          error: { code: "network_error", message: copy.networkError },
        });
      }
    }
  }

  return (
    <View testID="create-league-panel">
      {form.status === "loading" ? (
        <ActivityIndicator color={colors.ok} testID="league-status" />
      ) : null}
      {form.status === "empty" ? (
        <Text style={styles.muted} testID="league-empty">
          {copy.leagueEmptyForm}
        </Text>
      ) : null}
      {form.status === "error" && form.error ? (
        <Text style={styles.error} testID="league-error">
          {form.error.message}
        </Text>
      ) : null}
      {form.status === "success" && form.message ? (
        <Text style={styles.success} testID="league-success">
          {form.message}
        </Text>
      ) : null}

      {!emailVerified ? (
        <View testID="league-verify-required">
          <Text style={styles.warning}>{copy.emailNotVerified}</Text>
          <Text style={styles.muted}>{copy.emailNotVerifiedHint}</Text>
          {onVerifyEmail ? (
            <Pressable style={styles.button} onPress={onVerifyEmail}>
              <Text style={styles.buttonLabel}>{copy.goVerifyEmail}</Text>
            </Pressable>
          ) : null}
        </View>
      ) : null}

      <TextInput
        testID="league-name"
        value={name}
        onChangeText={setName}
        placeholder={copy.leagueName}
        placeholderTextColor={colors.muted}
        style={styles.input}
      />
      <TextInput
        testID="league-season-year"
        value={seasonYear}
        onChangeText={setSeasonYear}
        placeholder={copy.seasonYear}
        placeholderTextColor={colors.muted}
        keyboardType="number-pad"
        style={styles.input}
      />

      <Text style={styles.label}>{copy.competitions}</Text>
      <Text style={styles.muted}>{copy.selectCompetitionsHint(MIN_LEAGUE_COMPETITIONS)}</Text>
      {catalog.map((item) => (
        <Pressable
          key={item.id}
          onPress={() => toggleCompetition(item.id)}
          testID={`league-competition-${item.provider_id}`}
        >
          <Text style={styles.value}>
            {selected.has(item.id) ? "[x] " : "[ ] "}
            {item.name} ({item.country})
          </Text>
        </Pressable>
      ))}

      <Pressable
        style={[styles.button, !emailVerified ? styles.buttonDisabled : null]}
        onPress={() => void handleSubmit()}
        testID="league-submit"
        disabled={!emailVerified}
      >
        <Text style={styles.buttonLabel}>{copy.createLeague}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  muted: {
    color: colors.muted,
    marginBottom: spacing.sm,
  },
  error: {
    color: "#f87171",
    marginBottom: spacing.sm,
  },
  warning: {
    color: "#fbbf24",
    marginBottom: spacing.sm,
  },
  success: {
    color: colors.ok,
    marginBottom: spacing.sm,
  },
  label: {
    color: colors.muted,
    fontSize: typography.fontSize.sm,
    marginTop: spacing.sm,
  },
  value: {
    color: colors.foreground,
    fontSize: typography.fontSize.md,
    marginBottom: spacing.xs,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.muted,
    borderRadius: 8,
    padding: spacing.sm,
    color: colors.foreground,
    marginBottom: spacing.sm,
  },
  button: {
    backgroundColor: colors.ok,
    borderRadius: 8,
    padding: spacing.sm,
    alignItems: "center",
    marginTop: spacing.sm,
  },
  buttonDisabled: {
    backgroundColor: colors.muted,
  },
  buttonLabel: {
    color: colors.background,
    fontWeight: "600",
  },
});
