import { formatFantasyPoints } from "@fantappero/contracts";
import type { FantasyCoachProfile } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useNavigation, useRoute, type RouteProp } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useCallback, useState } from "react";
import { Image, Pressable, StyleSheet, Text, View } from "react-native";
import { fetchCoachProfile } from "../api/managerInvites";
import { UiStatePanel } from "../components/UiStatePanel";
import { useScreenData } from "../hooks/useScreenData";
import { PageContainer } from "../layout/PageContainer";
import type { RootStackParamList } from "../navigation/types";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";
import { resolveAvatarUrl } from "../utils/avatar";

const { colors, spacing, typography, radius } = theme;

/** Profilo storico limitato di un fantallenatore — porting mobile di CoachProfilePage (EP13-P06). */
export function CoachProfileScreen() {
  const route = useRoute<RouteProp<RootStackParamList, "CoachProfile">>();
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { accessToken, activeLeagueId } = useAuthSession();
  const userId = route.params.userId;
  const leagueId = route.params.leagueId ?? activeLeagueId;

  const [profile, setProfile] = useState<FantasyCoachProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!leagueId) {
      setLoading(false);
      setLoadError("Seleziona una lega amministrata per consultare il profilo.");
      return;
    }
    if (!accessToken) {
      setLoading(false);
      setLoadError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      setProfile(await fetchCoachProfile(accessToken, leagueId, userId));
    } catch (error) {
      setLoadError(getApiErrorMessage(error, "Impossibile caricare il profilo."));
      setProfile(null);
    } finally {
      setLoading(false);
    }
  }, [accessToken, leagueId, userId]);

  const { refreshing, onRefresh } = useScreenData(load);

  const avatarSrc = profile ? resolveAvatarUrl(profile.avatarUrl) : null;

  return (
    <PageContainer
      title={profile?.displayName ?? "Profilo fantallenatore"}
      testID="screen-coach-profile"
      refreshing={refreshing}
      onRefresh={onRefresh}
    >
      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento profilo"
          message="Recupero dei dati in corso…"
          testID="coach-profile-loading"
        />
      ) : null}

      {!loading && loadError ? (
        <UiStatePanel
          state="error"
          title="Profilo non disponibile"
          message={loadError}
          testID="coach-profile-error"
        />
      ) : null}

      {!loading && !loadError && profile ? (
        <View style={styles.card} testID="coach-profile">
          <View style={styles.header}>
            {avatarSrc ? (
              <Image source={{ uri: avatarSrc }} style={styles.avatarImage} />
            ) : (
              <View style={styles.avatarPlaceholder}>
                <Text style={styles.avatarInitial}>{profile.displayName.charAt(0)}</Text>
              </View>
            )}
            <View style={styles.headerText}>
              <Text style={styles.name}>{profile.displayName}</Text>
              <View style={styles.badgeRow}>
                <View style={styles.badge}>
                  <Text style={styles.badgeLabel}>
                    {profile.userType === "ai" ? "IA" : "Manuale"}
                  </Text>
                </View>
                <View style={[styles.badge, profile.availableForInvites && styles.badgeSuccess]}>
                  <Text style={styles.badgeLabel}>
                    {profile.availableForInvites ? "Disponibile" : "Non disponibile"}
                  </Text>
                </View>
                {profile.memberSince ? (
                  <Text style={styles.meta}>iscritto da {profile.memberSince}</Text>
                ) : null}
              </View>
            </View>
          </View>

          <Text style={styles.summary} testID="coach-profile-summary">
            {profile.historySummary}
          </Text>

          {profile.placements.length === 0 ? (
            <Text style={styles.meta} testID="coach-profile-empty">
              Nessuna lega conclusa: questo fantallenatore non ha ancora uno storico.
            </Text>
          ) : (
            <View testID="coach-profile-placements">
              {profile.placements.map((item) => (
                <Text
                  key={`${item.seasonYear}-${item.position}-${item.participantCount}`}
                  style={styles.placementRow}
                >
                  {item.seasonYear}: {item.position}º su {item.participantCount} ·{" "}
                  {item.played} partite · {item.points} punti ·{" "}
                  {formatFantasyPoints(item.fantasyPoints)} fantapunti
                </Text>
              ))}
            </View>
          )}

          <Text style={styles.hint}>
            Lo storico mostra solo leghe concluse. I nomi delle leghe non sono visibili.
          </Text>

          <Pressable
            accessibilityRole="button"
            onPress={() => navigation.goBack()}
            style={styles.button}
            testID="coach-profile-close"
          >
            <Text style={styles.buttonLabel}>Torna alla directory</Text>
          </Pressable>
        </View>
      ) : null}
    </PageContainer>
  );
}

const styles = StyleSheet.create({
  card: {
    gap: spacing.sm,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  avatarImage: {
    width: 56,
    height: 56,
    borderRadius: 28,
  },
  avatarPlaceholder: {
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.accentMuted,
  },
  avatarInitial: {
    fontSize: typography.fontSize.lg,
    fontWeight: typography.fontWeight.semibold,
    color: colors.background,
  },
  headerText: {
    flex: 1,
    gap: spacing.xs,
  },
  name: {
    color: colors.foreground,
    fontSize: typography.fontSize.lg,
    fontWeight: typography.fontWeight.semibold,
  },
  badgeRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    alignItems: "center",
    gap: spacing.xs,
  },
  badge: {
    backgroundColor: colors.backgroundElevated,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.xs,
    paddingVertical: 2,
  },
  badgeSuccess: {
    borderColor: colors.success,
  },
  badgeLabel: {
    fontSize: typography.fontSize.xs,
    fontWeight: typography.fontWeight.semibold,
    color: colors.foreground,
  },
  meta: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  summary: {
    color: colors.foreground,
    fontSize: typography.fontSize.md,
    fontWeight: typography.fontWeight.semibold,
  },
  placementRow: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    marginTop: spacing.xs,
  },
  hint: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.xs,
  },
  button: {
    marginTop: spacing.sm,
    alignSelf: "flex-start",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  buttonLabel: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
  },
});
