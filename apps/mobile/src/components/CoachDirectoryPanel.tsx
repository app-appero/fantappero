import { lazyStyles } from "../theme/lazyStyles";
import type { FantasyCoachDirectoryItem } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useCallback, useEffect, useState } from "react";
import { Image, Pressable, StyleSheet, Text, View } from "react-native";
import { AppTextInput as TextInput } from "./AppTextInput";
import { ApiError } from "../api/client";
import { createNamedLeagueInvite, fetchManagerDirectory } from "../api/managerInvites";
import type { RootStackParamList } from "../navigation/types";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";
import { resolveAvatarUrl } from "../utils/avatar";
import { UiStatePanel } from "./UiStatePanel";

const { colors, spacing, typography, radius } = theme;

function CoachAvatar({ name, avatarUrl }: { name: string; avatarUrl: string | null }) {
  const src = resolveAvatarUrl(avatarUrl);
  if (src) {
    return <Image source={{ uri: src }} style={styles.avatarImage} />;
  }
  return (
    <View style={styles.avatarPlaceholder}>
      <Text style={styles.avatarInitial}>{name.charAt(0)}</Text>
    </View>
  );
}

export type CoachDirectoryPanelProps = {
  leagueId: string;
  memberCount: number;
  capacity: number;
  testIDPrefix: string;
  /** Incrementato dal parent per forzare un reload (pull-to-refresh). */
  reloadToken?: number;
  /** Chiamato quando un reload richiesto via reloadToken è terminato. */
  onReloadSettled?: () => void;
  /** Ricarica iscritti e prerequisiti dopo un ingresso in lega o a capienza piena. */
  onMembershipChanged?: () => void;
};

/** Directory fantallenatori via API (come web ManagerDirectory). */
export function CoachDirectoryPanel({
  leagueId,
  memberCount,
  capacity,
  testIDPrefix,
  reloadToken,
  onReloadSettled,
  onMembershipChanged,
}: CoachDirectoryPanelProps) {
  const { accessToken, can } = useAuthSession();
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [items, setItems] = useState<FantasyCoachDirectoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [workingId, setWorkingId] = useState<string | null>(null);
  const [capacityReached, setCapacityReached] = useState(false);
  const leagueFull = capacity > 0 && (capacityReached || memberCount >= capacity);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query.trim()), 300);
    return () => clearTimeout(timer);
  }, [query]);

  const load = useCallback(
    async (options?: { silent?: boolean }) => {
      if (!options?.silent) {
        setSuccess(null);
        setInviteError(null);
      }
      if (!can(["league:admin"])) {
        setLoadError("Solo l’amministratore della lega può consultare la directory.");
        setItems([]);
        setLoading(false);
        return;
      }
      if (!accessToken) {
        setLoadError("Sessione non disponibile. Accedi di nuovo.");
        setItems([]);
        setLoading(false);
        return;
      }
      if (!options?.silent) {
        setLoading(true);
      }
      setLoadError(null);
      try {
        const first = await fetchManagerDirectory(accessToken, leagueId, {
          query: debouncedQuery || undefined,
          page: 1,
          pageSize: 50,
        });
        const collected = [...first.items];
        const lastPage = Math.min(first.totalPages, 10);
        for (let page = 2; page <= lastPage; page += 1) {
          const next = await fetchManagerDirectory(accessToken, leagueId, {
            query: debouncedQuery || undefined,
            page,
            pageSize: 50,
          });
          collected.push(...next.items);
        }
        setItems(collected);
      } catch (directoryError) {
        if (directoryError instanceof ApiError && directoryError.status === 403) {
          setLoadError("Non hai i permessi per consultare la directory.");
        } else {
          setLoadError(getApiErrorMessage(directoryError, "Impossibile caricare la directory."));
        }
        setItems([]);
      } finally {
        setLoading(false);
      }
    },
    [accessToken, can, debouncedQuery, leagueId],
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

  function openProfile(coach: FantasyCoachDirectoryItem) {
    navigation.navigate("CoachProfile", { userId: coach.userId, leagueId });
  }

  async function onInvite(manager: FantasyCoachDirectoryItem) {
    setInviteError(null);
    setSuccess(null);
    if (manager.isSelf || manager.inLeague || manager.emailVerified === false) {
      return;
    }
    if (!manager.availableForInvites) {
      setInviteError("Questo fantallenatore non accetta inviti.");
      return;
    }
    if (manager.namedInviteStatus === "pending") {
      setInviteError("Hai già invitato questo fantallenatore.");
      return;
    }
    if (leagueFull) {
      return;
    }
    if (!accessToken) {
      setInviteError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setWorkingId(manager.userId);
    try {
      const created = await createNamedLeagueInvite(accessToken, leagueId, manager.userId);
      setSuccess(
        created.autoAccepted
          ? `${manager.displayName} è entrato automaticamente nella lega.`
          : `Invito inviato a ${manager.displayName}.`,
      );
      await load({ silent: true });
      if (created.autoAccepted) {
        onMembershipChanged?.();
      }
    } catch (error) {
      if (error instanceof ApiError && error.code === "league_full") {
        setCapacityReached(true);
        onMembershipChanged?.();
        return;
      }
      setInviteError(getApiErrorMessage(error, "Impossibile inviare l'invito."));
    } finally {
      setWorkingId(null);
    }
  }

  return (
    <View style={styles.section} testID={loadError ? undefined : `${testIDPrefix}-success`}>
      <TextInput
        value={query}
        onChangeText={setQuery}
        placeholder="Cerca per nome o email"
        placeholderTextColor={colors.foregroundMuted}
        autoCapitalize="none"
        autoCorrect={false}
        style={styles.search}
        testID={`${testIDPrefix}-search`}
      />
      <Text style={styles.hint}>
        Tutti i fantallenatori della piattaforma, non solo quelli di questa lega.
        {capacity > 0 ? ` Posti ${memberCount}/${capacity}.` : ""}
      </Text>
      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento directory"
          message="Recupero di tutti i fantallenatori…"
          testID={`${testIDPrefix}-loading`}
        />
      ) : null}
      {!loading && loadError && items.length === 0 ? (
        <View>
          <UiStatePanel
            state="error"
            title="Directory non disponibile"
            message={loadError}
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
      ) : null}
      {!loading && !(loadError && items.length === 0) ? (
        <>
      {success ? (
        <UiStatePanel
          state="success"
          title="Invito nominativo inviato"
          message={success}
          testID={`${testIDPrefix}-invite-success`}
        />
      ) : null}
      {leagueFull ? (
        <UiStatePanel
          state="empty"
          title="Lega al completo"
          message="La lega è al completo: non puoi inviare altri inviti. La directory resta consultabile."
          testID={`${testIDPrefix}-capacity`}
        />
      ) : null}
      {inviteError ? (
        <UiStatePanel
          state="error"
          title="Invito non riuscito"
          message={inviteError}
          testID={`${testIDPrefix}-invite-error`}
        />
      ) : null}
      {items.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Nessun fantallenatore trovato"
          message="Nessun fantallenatore corrisponde alla ricerca."
          testID={`${testIDPrefix}-empty`}
        />
      ) : (
        items.map((coach) => {
          const pending = coach.namedInviteStatus === "pending";
          const unavailable = !coach.availableForInvites;
          const inLeague = coach.inLeague === true;
          const isSelf = coach.isSelf === true;
          const unverified = coach.emailVerified === false;
          const inviteBlocked =
            isSelf ||
            pending ||
            unavailable ||
            unverified ||
            inLeague ||
            leagueFull ||
            workingId === coach.userId;
          const inviteLabel = isSelf
            ? "Sei tu"
            : inLeague
              ? "Già in lega"
              : unverified
                ? "Non verificato"
                : unavailable
                  ? "Indisponibile"
                  : pending
                    ? "Già invitato"
                    : "Invita";
          return (
            <View key={coach.userId} style={styles.card}>
              <CoachAvatar name={coach.displayName} avatarUrl={coach.avatarUrl} />
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={`Apri il profilo di ${coach.displayName}`}
                onPress={() => openProfile(coach)}
                style={styles.identity}
                testID={`${testIDPrefix}-open-${coach.userId}`}
              >
                <Text style={styles.name}>{coach.displayName}</Text>
                <Text style={styles.status}>{coach.email}</Text>
                <Text style={styles.status}>
                  {coach.userType === "ai" ? "IA" : "Manuale"} ·{" "}
                  {isSelf
                    ? "Sei tu"
                    : inLeague
                      ? "Già in lega"
                      : unverified
                        ? "Email non verificata"
                        : coach.availableForInvites
                          ? "Disponibile"
                          : "Non disponibile"}
                  {coach.memberSince ? ` · dal ${coach.memberSince}` : ""}
                </Text>
                <Text style={styles.status} testID={`${testIDPrefix}-history-${coach.userId}`}>
                  {coach.historySummary}
                </Text>
              </Pressable>
              <Pressable
                accessibilityRole="button"
                disabled={inviteBlocked}
                onPress={() => void onInvite(coach)}
                style={[styles.button, inviteBlocked && styles.buttonDisabled]}
                testID={`${testIDPrefix}-invite-${coach.userId}`}
              >
                <Text style={styles.buttonLabel}>{inviteLabel}</Text>
              </Pressable>
            </View>
          );
        })
      )}
        </>
      ) : null}
    </View>
  );
}

const styles = lazyStyles(() => StyleSheet.create({
  section: {
    gap: spacing.sm,
  },
  hint: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  search: {
    minHeight: 44,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    color: colors.foreground,
    backgroundColor: colors.background,
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
  avatarImage: {
    width: 40,
    height: 40,
    borderRadius: 20,
  },
  avatarPlaceholder: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.accentMuted,
  },
  avatarInitial: {
    fontWeight: typography.fontWeight.semibold,
    color: colors.background,
  },
}));
