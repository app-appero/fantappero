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
      <Text style={styles.avatarInitial}>{name.charAt(0).toUpperCase()}</Text>
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
  const [onlyAvailable, setOnlyAvailable] = useState(false);
  const [page, setPage] = useState(0);
  const leagueFull = capacity > 0 && (capacityReached || memberCount >= capacity);

  const visibleItems = onlyAvailable
    ? items.filter((coach) => coach.availableForInvites && !coach.inLeague && !coach.isSelf && coach.emailVerified !== false)
    : items;
  const pageCount = Math.max(1, Math.ceil(visibleItems.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const pagedItems = visibleItems.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE);

  useEffect(() => {
    setPage(0);
  }, [debouncedQuery, onlyAvailable]);

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
      <View style={styles.panel}>
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
        <Pressable
          style={styles.checkRow}
          onPress={() => setOnlyAvailable((current) => !current)}
          accessibilityRole="checkbox"
          accessibilityState={{ checked: onlyAvailable }}
          testID={`${testIDPrefix}-only-available`}
        >
          <View style={[styles.checkBox, onlyAvailable && styles.checkBoxOn]}>
            {onlyAvailable ? <Text style={styles.checkMark}>✓</Text> : null}
          </View>
          <Text style={styles.checkLabel}>Solo disponibili</Text>
        </Pressable>
        <Text style={styles.hint}>
          Tutti i fantallenatori della piattaforma, non solo quelli di questa lega.
          {capacity > 0 ? ` Posti ${memberCount}/${capacity}.` : ""}
        </Text>
      </View>
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
      {visibleItems.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Nessun fantallenatore trovato"
          message="Nessun fantallenatore corrisponde alla ricerca."
          testID={`${testIDPrefix}-empty`}
        />
      ) : (
        <>
        <Text style={styles.count} testID={`${testIDPrefix}-count`}>
          {visibleItems.length} {visibleItems.length === 1 ? "fantallenatore" : "fantallenatori"}
        </Text>
        {pagedItems.map((coach) => {
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
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={`Apri il profilo di ${coach.displayName}`}
                onPress={() => openProfile(coach)}
                style={styles.cardTop}
                testID={`${testIDPrefix}-open-${coach.userId}`}
              >
                <CoachAvatar name={coach.displayName} avatarUrl={coach.avatarUrl} />
                <View style={styles.identity}>
                  <Text style={styles.name}>{coach.displayName}</Text>
                  <Text style={styles.email}>{coach.email}</Text>
                </View>
              </Pressable>
              <View style={styles.chips}>
                <Text style={styles.chip}>{coach.userType === "ai" ? "IA" : "MANUALE"}</Text>
                <Text
                  style={[
                    styles.chip,
                    isSelf || inLeague || unverified || unavailable ? styles.chipMuted : styles.chipOk,
                  ]}
                >
                  {(isSelf
                    ? "Sei tu"
                    : inLeague
                      ? "Già in lega"
                      : unverified
                        ? "Email non verificata"
                        : coach.availableForInvites
                          ? "Disponibile"
                          : "Non disponibile"
                  ).toUpperCase()}
                </Text>
                {coach.memberSince ? <Text style={styles.since}>dal {coach.memberSince}</Text> : null}
              </View>
              <Text style={styles.history} testID={`${testIDPrefix}-history-${coach.userId}`}>
                {coach.historySummary}
              </Text>
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
        })}
        {pageCount > 1 ? (
          <View style={styles.pager} testID={`${testIDPrefix}-pager`}>
            <Pressable
              style={[styles.pagerButton, safePage === 0 && styles.buttonDisabled]}
              disabled={safePage === 0}
              onPress={() => setPage(safePage - 1)}
            >
              <Text style={styles.pagerLabel}>Precedente</Text>
            </Pressable>
            <Text style={styles.hint}>
              Pagina {safePage + 1} di {pageCount}
            </Text>
            <Pressable
              style={[styles.pagerButton, safePage >= pageCount - 1 && styles.buttonDisabled]}
              disabled={safePage >= pageCount - 1}
              onPress={() => setPage(safePage + 1)}
            >
              <Text style={styles.pagerLabel}>Successiva</Text>
            </Pressable>
          </View>
        ) : null}
        </>
      )}
        </>
      ) : null}
    </View>
  );
}

const PAGE_SIZE = 10;

const styles = lazyStyles(() => StyleSheet.create({
  section: {
    gap: spacing.sm,
  },
  checkRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  checkBox: {
    width: 24,
    height: 24,
    borderRadius: 7,
    borderWidth: 1.5,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  checkBoxOn: { backgroundColor: colors.brand, borderColor: colors.brand },
  checkMark: { color: colors.onBrand, fontWeight: "800" },
  checkLabel: { color: colors.foreground, fontWeight: "600" },
  pager: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.sm },
  pagerButton: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
  },
  pagerLabel: { color: colors.foreground, fontWeight: "600" },
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
  panel: {
    gap: spacing.sm,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.xl,
    backgroundColor: colors.backgroundElevated,
    marginBottom: spacing.sm,
  },
  count: {
    color: colors.foreground,
    fontSize: typography.fontSize.xl,
    fontStyle: "italic",
    fontWeight: "800",
    textTransform: "uppercase",
    marginTop: spacing.xs,
  },
  card: {
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.xl,
    backgroundColor: colors.backgroundElevated,
    gap: spacing.sm,
    marginBottom: spacing.xs,
  },
  cardTop: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.md,
  },
  identity: {
    flex: 1,
    minWidth: 0,
    gap: 2,
  },
  email: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    flexShrink: 1,
  },
  chips: {
    flexDirection: "row",
    flexWrap: "wrap",
    alignItems: "center",
    gap: spacing.xs,
  },
  chip: {
    color: colors.foreground,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.6,
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 999,
    overflow: "hidden",
    backgroundColor: "rgba(255,255,255,0.1)",
  },
  chipOk: { backgroundColor: "rgba(52,211,153,0.22)", color: colors.success },
  chipMuted: { backgroundColor: "rgba(156,163,175,0.2)" },
  since: { color: colors.foregroundMuted, fontSize: typography.fontSize.sm },
  history: { color: colors.foregroundMuted, fontSize: typography.fontSize.sm },
  name: {
    color: colors.foreground,
    fontWeight: "700",
    fontSize: typography.fontSize.lg,
  },
  status: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    marginTop: spacing.xs,
  },
  button: {
    minHeight: 46,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.md,
    borderRadius: radius.pill,
    backgroundColor: colors.brand,
  },
  buttonDisabled: {
    opacity: 0.55,
  },
  buttonLabel: {
    color: colors.onBrand,
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
    width: 48,
    height: 48,
    borderRadius: 24,
  },
  avatarPlaceholder: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.brand,
    borderWidth: 2,
    borderColor: colors.accentSecondary,
  },
  avatarInitial: {
    fontWeight: "800",
    fontStyle: "italic",
    textAlign: "center",
    paddingHorizontal: 4,
    color: colors.onBrand,
  },
}));
