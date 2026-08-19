import type { FantasyCoachDirectoryItem } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useFocusEffect } from "@react-navigation/native";
import { useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { ApiError } from "../api/client";
import { createNamedLeagueInvite, fetchManagerDirectory } from "../api/managerInvites";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";
import { UiStatePanel } from "./UiStatePanel";

const { colors, spacing, typography, radius } = theme;

export type CoachDirectoryPanelProps = {
  leagueId: string;
  memberCount: number;
  capacity: number;
  testIDPrefix: string;
  /** Incrementato dal parent per forzare un reload (pull-to-refresh). */
  reloadToken?: number;
  /** Chiamato quando un reload richiesto via reloadToken è terminato. */
  onReloadSettled?: () => void;
};

/** Directory fantallenatori via API (come web ManagerDirectory). */
export function CoachDirectoryPanel({
  leagueId,
  memberCount,
  capacity,
  testIDPrefix,
  reloadToken,
  onReloadSettled,
}: CoachDirectoryPanelProps) {
  const { accessToken, can } = useAuthSession();
  const [items, setItems] = useState<FantasyCoachDirectoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [workingId, setWorkingId] = useState<string | null>(null);

  const load = useCallback(
    async (options?: { silent?: boolean }) => {
      setSuccess(null);
      if (!can(["league:admin"])) {
        setError("Solo l’amministratore della lega può consultare la directory.");
        setItems([]);
        setLoading(false);
        return;
      }
      if (!accessToken) {
        setError("Sessione non disponibile. Accedi di nuovo.");
        setItems([]);
        setLoading(false);
        return;
      }
      if (!options?.silent) {
        setLoading(true);
      }
      setError(null);
      try {
        const page = await fetchManagerDirectory(accessToken, leagueId, { pageSize: 20 });
        setItems(page.items);
      } catch (loadError) {
        if (loadError instanceof ApiError && loadError.status === 403) {
          setError("Non hai i permessi per consultare la directory.");
        } else {
          setError(getApiErrorMessage(loadError, "Impossibile caricare la directory."));
        }
        setItems([]);
      } finally {
        setLoading(false);
      }
    },
    [accessToken, can, leagueId],
  );

  useFocusEffect(
    useCallback(() => {
      void load({ silent: true });
    }, [load]),
  );

  useEffect(() => {
    if (reloadToken === undefined || reloadToken === 0) {
      return;
    }
    let cancelled = false;
    void (async () => {
      await load({ silent: true });
      if (!cancelled) {
        onReloadSettled?.();
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [load, onReloadSettled, reloadToken]);

  async function onInvite(manager: FantasyCoachDirectoryItem) {
    setError(null);
    setSuccess(null);
    if (!manager.availableForInvites) {
      setError("Questo fantallenatore non accetta inviti.");
      return;
    }
    if (manager.namedInviteStatus === "pending") {
      setError("Hai già invitato questo fantallenatore.");
      return;
    }
    if (memberCount >= capacity) {
      setError("La lega ha raggiunto la capienza massima.");
      return;
    }
    if (!accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setWorkingId(manager.userId);
    try {
      await createNamedLeagueInvite(accessToken, leagueId, manager.userId);
      setSuccess(`Invito inviato a ${manager.displayName}.`);
      await load({ silent: true });
    } catch (inviteError) {
      setError(getApiErrorMessage(inviteError, "Impossibile inviare l'invito."));
    } finally {
      setWorkingId(null);
    }
  }

  if (loading) {
    return (
      <UiStatePanel
        state="loading"
        title="Caricamento directory"
        message="Recupero dei fantallenatori disponibili…"
        testID={`${testIDPrefix}-loading`}
      />
    );
  }

  if (error && items.length === 0) {
    return (
      <View style={styles.section}>
        <UiStatePanel
          state="error"
          title="Directory non disponibile"
          message={error}
          testID={`${testIDPrefix}-error`}
        />
        <Pressable
          accessibilityRole="button"
          onPress={() => void load()}
          style={styles.retry}
          testID={`${testIDPrefix}-retry`}
        >
          <Text style={styles.retryLabel}>Ricarica</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.section} testID={`${testIDPrefix}-success`}>
      <Text style={styles.hint}>
        Fantallenatori disponibili agli inviti. Posti {memberCount}/{capacity}.
      </Text>
      {success ? (
        <UiStatePanel
          state="success"
          title="Invito nominativo inviato"
          message={success}
          testID={`${testIDPrefix}-invite-success`}
        />
      ) : null}
      {error ? (
        <UiStatePanel
          state="error"
          title="Invito non riuscito"
          message={error}
          testID={`${testIDPrefix}-invite-error`}
        />
      ) : null}
      {items.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Directory vuota"
          message="Nessun fantallenatore ha attivato la disponibilità."
          testID={`${testIDPrefix}-empty`}
        />
      ) : (
        items.map((coach) => {
          const pending = coach.namedInviteStatus === "pending";
          const unavailable = !coach.availableForInvites;
          return (
            <View key={coach.userId} style={styles.card}>
              <View style={styles.identity}>
                <Text style={styles.name}>{coach.displayName}</Text>
                <Text style={styles.status}>
                  {coach.userType === "ai" ? "IA" : "Manuale"} ·{" "}
                  {coach.availableForInvites ? "Disponibile" : "Non disponibile"}
                </Text>
              </View>
              <Pressable
                accessibilityRole="button"
                disabled={pending || unavailable || workingId === coach.userId}
                onPress={() => void onInvite(coach)}
                style={[
                  styles.button,
                  (pending || unavailable || workingId === coach.userId) && styles.buttonDisabled,
                ]}
                testID={`${testIDPrefix}-invite-${coach.userId}`}
              >
                <Text style={styles.buttonLabel}>
                  {unavailable ? "Indisponibile" : pending ? "Già invitato" : "Invita"}
                </Text>
              </Pressable>
            </View>
          );
        })
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  section: {
    gap: spacing.sm,
  },
  hint: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  card: {
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.backgroundElevated,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  identity: {
    flex: 1,
  },
  name: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
  },
  status: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    marginTop: spacing.xs,
  },
  button: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    backgroundColor: colors.accent,
  },
  buttonDisabled: {
    opacity: 0.55,
  },
  buttonLabel: {
    color: colors.accentContrast,
    fontWeight: typography.fontWeight.semibold,
  },
  retry: {
    minHeight: 44,
    alignItems: "center",
    justifyContent: "center",
  },
  retryLabel: {
    color: colors.accent,
    fontWeight: typography.fontWeight.semibold,
  },
});
