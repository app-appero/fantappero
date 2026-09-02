import type { NamedLeagueInvite } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useNavigation } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useCallback, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import {
  acceptReceivedNamedInvite,
  declineReceivedNamedInvite,
  fetchReceivedNamedInvites,
} from "../api/managerInvites";
import { UiStatePanel } from "../components/UiStatePanel";
import { useScreenData } from "../hooks/useScreenData";
import { PageContainer } from "../layout/PageContainer";
import type { RootStackParamList } from "../navigation/types";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";

const { colors, spacing, typography, radius } = theme;

export function ReceivedInvitesScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { can, accessToken, registerLeague, refreshMemberships } = useAuthSession();

  const [invites, setInvites] = useState<NamedLeagueInvite[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [workingId, setWorkingId] = useState<string | null>(null);

  const loadInvites = useCallback(
    async (options?: { silent?: boolean }) => {
      if (!accessToken) {
        setError("Sessione non disponibile. Accedi di nuovo.");
        setLoading(false);
        return;
      }
      if (!options?.silent) {
        setLoading(true);
      }
      setError(null);
      try {
        const rows = await fetchReceivedNamedInvites(accessToken);
        setInvites(rows.filter((invite) => invite.status === "pending"));
      } catch (loadError) {
        setError(getApiErrorMessage(loadError, "Impossibile caricare gli inviti ricevuti."));
      } finally {
        setLoading(false);
      }
    },
    [accessToken],
  );

  const { refreshing, onRefresh } = useScreenData(loadInvites);

  if (!can(["league:view"])) {
    return (
      <PageContainer title="Inviti ricevuti" testID="screen-received-invites">
        <UiStatePanel
          state="forbidden"
          title="Permessi insufficienti"
          message="Questa sessione non può consultare gli inviti ricevuti."
          testID="received-invites-forbidden"
        />
      </PageContainer>
    );
  }

  async function onAccept(invite: NamedLeagueInvite) {
    setFeedback(null);
    setError(null);
    if (!accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setWorkingId(invite.id);
    try {
      const responded = await acceptReceivedNamedInvite(accessToken, invite.id);
      setInvites((current) => current.filter((row) => row.id !== invite.id));
      registerLeague({
        id: responded.leagueId,
        name: responded.leagueName,
        role: "member",
      });
      try {
        await refreshMemberships();
      } catch {
        // Accettazione già riuscita.
      }
      setFeedback(`Hai accettato l’invito a ${responded.leagueName}.`);
      navigation.navigate("LeagueHome", { leagueId: responded.leagueId });
    } catch (acceptError) {
      setError(getApiErrorMessage(acceptError, "Impossibile aggiornare l'invito."));
    } finally {
      setWorkingId(null);
    }
  }

  async function onDecline(invite: NamedLeagueInvite) {
    setFeedback(null);
    setError(null);
    if (!accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setWorkingId(invite.id);
    try {
      await declineReceivedNamedInvite(accessToken, invite.id);
      setInvites((current) => current.filter((row) => row.id !== invite.id));
      setFeedback(`Hai rifiutato l’invito a ${invite.leagueName}.`);
    } catch (declineError) {
      setError(getApiErrorMessage(declineError, "Impossibile aggiornare l'invito."));
    } finally {
      setWorkingId(null);
    }
  }

  return (
    <PageContainer
      title="Inviti ricevuti"
      testID="screen-received-invites"
      refreshing={refreshing}
      onRefresh={onRefresh}
    >
      <Text style={styles.hint}>
        Accetta o rifiuta gli inviti nominativi ricevuti dagli amministratori di lega.
      </Text>
      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento inviti"
          message="Recupero degli inviti in corso…"
          testID="received-invites-loading"
        />
      ) : null}
      {error ? (
        <UiStatePanel
          state="error"
          title="Inviti non disponibili"
          message={error}
          testID="received-invites-error"
        />
      ) : null}
      {feedback ? (
        <UiStatePanel
          state="success"
          title="Invito aggiornato"
          message={feedback}
          testID="received-invites-action-success"
        />
      ) : null}
      {!loading && !error && invites.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Nessun invito in attesa"
          message="Non hai inviti nominativi in attesa."
          testID="received-invites-empty"
        />
      ) : null}
      {!loading && invites.length > 0 ? (
        <View style={styles.list} testID="received-invites-list">
          {invites.map((invite) => (
            <View key={invite.id} style={styles.card}>
              <Text style={styles.name}>{invite.leagueName}</Text>
              <Text style={styles.hint}>Invito nominativo</Text>
              <View style={styles.actions}>
                <Pressable
                  accessibilityRole="button"
                  disabled={workingId === invite.id}
                  onPress={() => void onAccept(invite)}
                  style={styles.primaryButton}
                  testID={`received-invite-accept-${invite.id}`}
                >
                  <Text style={styles.primaryLabel}>Accetta</Text>
                </Pressable>
                <Pressable
                  accessibilityRole="button"
                  disabled={workingId === invite.id}
                  onPress={() => void onDecline(invite)}
                  style={styles.secondaryButton}
                  testID={`received-invite-decline-${invite.id}`}
                >
                  <Text style={styles.secondaryLabel}>Rifiuta</Text>
                </Pressable>
              </View>
            </View>
          ))}
        </View>
      ) : null}
    </PageContainer>
  );
}

const styles = StyleSheet.create({
  hint: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  list: {
    gap: spacing.sm,
  },
  card: {
    gap: spacing.sm,
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
  actions: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  primaryButton: {
    minHeight: 44,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    backgroundColor: colors.accent,
    justifyContent: "center",
  },
  primaryLabel: {
    color: colors.accentContrast,
    fontWeight: typography.fontWeight.semibold,
  },
  secondaryButton: {
    minHeight: 44,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    justifyContent: "center",
  },
  secondaryLabel: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
  },
});
