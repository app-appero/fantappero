import type { LeagueSummary } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useNavigation } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useCallback, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { deleteLeague } from "../api/leagues";
import { UiStatePanel } from "../components/UiStatePanel";
import { useScreenData } from "../hooks/useScreenData";
import { PageContainer } from "../layout/PageContainer";
import { isLeagueDeletable } from "../leagues/leagueDeleteHelpers";
import { leagueStateLabel } from "../leagues/leagueLabels";
import type { RootStackParamList } from "../navigation/types";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";

const { colors, spacing, typography, radius } = theme;

/** Dashboard leghe M1: entra, admin, elimina bozza, azioni rapide (EP03-UX-01). */
export function LeaguesScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { accessToken, setActiveLeagueId, unregisterLeague, refreshMemberships } =
    useAuthSession();
  const [leagues, setLeagues] = useState<LeagueSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [deleteConfirmed, setDeleteConfirmed] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const loadLeagues = useCallback(
    async (options?: { silent?: boolean }) => {
      if (!accessToken) {
        setLoadError("Sessione non disponibile. Accedi di nuovo.");
        setLoading(false);
        return;
      }
      if (!options?.silent) {
        setLoading(true);
      }
      setLoadError(null);
      try {
        setLeagues(await refreshMemberships());
      } catch (error) {
        setLoadError(getApiErrorMessage(error, "Impossibile caricare le leghe."));
      } finally {
        setLoading(false);
      }
    },
    [accessToken, refreshMemberships],
  );

  const { refreshing, onRefresh } = useScreenData(loadLeagues);

  function enterLeague(league: LeagueSummary) {
    setActiveLeagueId(league.id);
    navigation.navigate("LeagueHome", { leagueId: league.id });
  }

  function beginDelete(leagueId: string) {
    setDeleteError(null);
    setDeleteConfirmed(false);
    setPendingDeleteId(leagueId);
  }

  function cancelDelete() {
    setPendingDeleteId(null);
    setDeleteConfirmed(false);
    setDeleteError(null);
  }

  async function confirmDelete(league: LeagueSummary) {
    setDeleteError(null);
    if (!deleteConfirmed) {
      setDeleteError("Conferma esplicitamente l'eliminazione spuntando la casella.");
      return;
    }
    if (!accessToken) {
      setDeleteError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setDeletingId(league.id);
    try {
      await deleteLeague(accessToken, league.id);
      unregisterLeague(league.id);
      setLeagues(await refreshMemberships());
      cancelDelete();
    } catch (error) {
      setDeleteError(getApiErrorMessage(error, "Impossibile eliminare la lega."));
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <PageContainer
      title="Le tue leghe"
      testID="screen-leagues"
      refreshing={refreshing}
      onRefresh={onRefresh}
    >
      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento leghe"
          message="Recupero delle leghe in corso…"
          testID="leagues-loading"
        />
      ) : null}

      {!loading && loadError ? (
        <UiStatePanel
          state="error"
          title="Errore di caricamento"
          message={loadError}
          testID="leagues-error"
        />
      ) : null}

      {!loading && !loadError && leagues.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Nessuna lega"
          message="Non partecipi ancora a nessuna lega privata. Creane una oppure unisciti con un codice invito."
          testID="leagues-empty"
        />
      ) : null}

      {!loading && !loadError && leagues.length > 0 ? (
        <View style={styles.list} testID="leagues-list">
          {leagues.map((league) => {
            const canDelete =
              league.role === "league_admin" && isLeagueDeletable(league.state);
            const isPending = pendingDeleteId === league.id;
            return (
              <View key={league.id} style={styles.card} testID={`league-card-${league.id}`}>
                <Text style={styles.name}>{league.name}</Text>
                <Text style={styles.meta}>
                  Ruolo:{" "}
                  {league.role === "league_admin" ? "Amministratore" : "Partecipante"}
                </Text>
                <Text style={styles.meta}>Stato: {leagueStateLabel(league.state)}</Text>
                <View style={styles.actions}>
                  <Pressable
                    accessibilityRole="button"
                    accessibilityLabel={`Entra in ${league.name}`}
                    onPress={() => enterLeague(league)}
                    style={styles.primaryButton}
                    testID={`league-enter-${league.id}`}
                  >
                    <Text style={styles.primaryLabel}>Entra in lega</Text>
                  </Pressable>
                  {league.role === "league_admin" ? (
                    <Pressable
                      accessibilityRole="button"
                      accessibilityLabel={`Amministrazione ${league.name}`}
                      onPress={() => {
                        setActiveLeagueId(league.id);
                        navigation.navigate("LeagueAdmin", { leagueId: league.id });
                      }}
                      style={styles.ghostButton}
                      testID={`league-admin-link-${league.id}`}
                    >
                      <Text style={styles.ghostLabel}>Amministrazione lega</Text>
                    </Pressable>
                  ) : null}
                  {canDelete && !isPending ? (
                    <Pressable
                      accessibilityRole="button"
                      accessibilityLabel={`Elimina ${league.name}`}
                      onPress={() => beginDelete(league.id)}
                      style={styles.dangerButton}
                      testID={`league-delete-${league.id}`}
                    >
                      <Text style={styles.dangerLabel}>Elimina lega</Text>
                    </Pressable>
                  ) : null}
                </View>
                {canDelete && isPending ? (
                  <View
                    style={styles.deletePanel}
                    testID={`league-delete-confirm-panel-${league.id}`}
                  >
                    <Text style={styles.meta}>
                      L'eliminazione è definitiva. Disponibile solo in bozza o configurazione.
                    </Text>
                    <Pressable
                      accessibilityRole="checkbox"
                      accessibilityState={{ checked: deleteConfirmed }}
                      accessibilityLabel={`Confermo di voler eliminare definitivamente ${league.name}`}
                      onPress={() => setDeleteConfirmed((value) => !value)}
                      style={styles.checkboxRow}
                      testID={`league-delete-confirm-${league.id}`}
                    >
                      <View
                        style={[styles.checkbox, deleteConfirmed && styles.checkboxChecked]}
                      />
                      <Text style={styles.meta}>
                        Confermo di voler eliminare definitivamente «{league.name}»
                      </Text>
                    </Pressable>
                    {deleteError ? (
                      <UiStatePanel
                        state="error"
                        title="Eliminazione non riuscita"
                        message={deleteError}
                        testID="leagues-delete-error"
                      />
                    ) : null}
                    <View style={styles.actions}>
                      <Pressable
                        accessibilityRole="button"
                        disabled={!deleteConfirmed || deletingId === league.id}
                        onPress={() => void confirmDelete(league)}
                        style={[
                          styles.dangerButton,
                          (!deleteConfirmed || deletingId === league.id) && styles.disabled,
                        ]}
                        testID={`league-delete-submit-${league.id}`}
                      >
                        <Text style={styles.dangerLabel}>Conferma eliminazione</Text>
                      </Pressable>
                      <Pressable
                        accessibilityRole="button"
                        onPress={cancelDelete}
                        style={styles.ghostButton}
                        testID={`league-delete-cancel-${league.id}`}
                      >
                        <Text style={styles.ghostLabel}>Annulla</Text>
                      </Pressable>
                    </View>
                  </View>
                ) : null}
              </View>
            );
          })}
        </View>
      ) : null}

      <View style={styles.footer}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Crea lega"
          onPress={() => navigation.navigate("CreateLeague")}
          style={styles.secondaryButton}
          testID="leagues-create-link"
        >
          <Text style={styles.secondaryLabel}>Crea lega</Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Unisciti con codice"
          onPress={() => navigation.navigate("JoinLeague")}
          style={styles.ghostButton}
          testID="leagues-join-link"
        >
          <Text style={styles.ghostLabel}>Unisciti con codice</Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Inviti ricevuti"
          onPress={() => navigation.navigate("ReceivedInvites")}
          style={styles.ghostButton}
          testID="mobile-leagues-received-invites"
        >
          <Text style={styles.ghostLabel}>Inviti ricevuti</Text>
        </Pressable>
        {!loading && loadError ? (
          <Pressable
            accessibilityRole="button"
            onPress={() => void loadLeagues()}
            style={styles.ghostButton}
            testID="leagues-retry"
          >
            <Text style={styles.ghostLabel}>Ricarica</Text>
          </Pressable>
        ) : null}
      </View>
    </PageContainer>
  );
}

const styles = StyleSheet.create({
  list: {
    gap: spacing.md,
  },
  card: {
    gap: spacing.xs,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.backgroundElevated,
  },
  name: {
    color: colors.foreground,
    fontSize: typography.fontSize.lg,
    fontWeight: typography.fontWeight.semibold,
  },
  meta: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  actions: {
    marginTop: spacing.sm,
    gap: spacing.sm,
  },
  footer: {
    marginTop: spacing.lg,
    gap: spacing.sm,
  },
  primaryButton: {
    minHeight: 44,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  primaryLabel: {
    color: colors.accentContrast,
    fontWeight: typography.fontWeight.semibold,
  },
  secondaryButton: {
    minHeight: 44,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  secondaryLabel: {
    color: colors.accent,
    fontWeight: typography.fontWeight.semibold,
  },
  ghostButton: {
    minHeight: 44,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
  },
  ghostLabel: {
    color: colors.accent,
    fontWeight: typography.fontWeight.semibold,
  },
  dangerButton: {
    minHeight: 44,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.danger,
    alignItems: "center",
    justifyContent: "center",
  },
  dangerLabel: {
    color: colors.danger,
    fontWeight: typography.fontWeight.semibold,
  },
  deletePanel: {
    marginTop: spacing.sm,
    gap: spacing.sm,
  },
  checkboxRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.sm,
  },
  checkbox: {
    width: 22,
    height: 22,
    marginTop: 2,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 4,
  },
  checkboxChecked: {
    backgroundColor: colors.accent,
    borderColor: colors.accent,
  },
  disabled: {
    opacity: 0.5,
  },
});
