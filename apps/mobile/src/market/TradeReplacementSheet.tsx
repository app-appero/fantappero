import {
  type FantasyRole,
  type TradeReplacementCandidate,
  type TradeReplacementOrder,
  type TradeReplacementPurchase,
  type TradeReplacementStatus,
  REPLACEMENT_CANCEL_LABEL,
  REPLACEMENT_CONFIRM_LABEL,
  REPLACEMENT_EMPTY_LIST,
  REPLACEMENT_LATER_LABEL,
  REPLACEMENT_LATER_NOTE,
  REPLACEMENT_ORDER_OPTIONS,
  REPLACEMENT_SEARCH_PLACEHOLDER,
  REPLACEMENT_SHEET_TITLE,
  REPLACEMENT_TOO_EXPENSIVE,
  replacementChips,
  replacementConfirmNote,
  replacementConfirmTitle,
  replacementCreditRows,
  replacementDoneBanner,
  replacementIntro,
  replacementRoles,
  replacementTakeLabel,
  replacementUnaffordableNotice,
  roleSingularLabel,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { buyTradeReplacement, fetchTradeReplacementCandidates } from "../api/market";
import { AppTextInput as TextInput } from "../components/AppTextInput";
import { getApiErrorMessage } from "../session/DemoSessionContext";
import { lazyStyles } from "../theme/lazyStyles";
import { AthleteMarketTags } from "./AthleteMarketTags";
import { ReplacementUnaffordableBox, shortfallStyles } from "./TradeShortfall";

const { colors, spacing, typography, radius } = theme;
const SEARCH_DEBOUNCE_MS = 300;

/**
 * Foglio dal basso «Scegli il sostituto» (1.5): dopo uno scambio che ha lasciato la rosa sotto la
 * misura la squadra sceglie un calciatore libero del ruolo che manca e lo paga il suo Valore.
 * Prima l'elenco dei liberi (ricerca e ordine per Valore), poi la conferma con il conto. Con due
 * posti da riempire si sceglie uno alla volta. «Più tardi» (o il tasto indietro) chiude.
 */
export function TradeReplacementSheet({
  visible,
  accessToken,
  leagueId,
  status,
  onClose,
  onPurchased,
}: {
  visible: boolean;
  accessToken: string | null;
  leagueId: string | null;
  status: TradeReplacementStatus | null;
  onClose: () => void;
  onPurchased: (purchase: TradeReplacementPurchase) => void;
}) {
  const roles = useMemo(() => replacementRoles(status?.missingRoles), [status]);
  const [role, setRole] = useState<FantasyRole | null>(null);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [order, setOrder] = useState<TradeReplacementOrder>("valore");
  const [candidates, setCandidates] = useState<TradeReplacementCandidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [target, setTarget] = useState<TradeReplacementCandidate | null>(null);
  const [buying, setBuying] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);
  const activeRole: FantasyRole | null = role && roles.includes(role) ? role : (roles[0] ?? null);
  const blocked = Boolean(status?.blockedMessage);

  useEffect(() => {
    if (!visible) {
      setTarget(null);
      setError(null);
      setSearch("");
      setDebouncedSearch("");
    }
  }, [visible]);

  useEffect(() => {
    const handle = setTimeout(() => setDebouncedSearch(search), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [search]);

  useEffect(() => {
    if (!visible || !accessToken || !leagueId || !activeRole) {
      return;
    }
    let cancelled = false;
    setLoading(true);
    void fetchTradeReplacementCandidates(accessToken, leagueId, { role: activeRole, search: debouncedSearch, order })
      .then((list) => {
        if (!cancelled) {
          setCandidates(list.candidates);
        }
      })
      .catch((cause) => {
        if (!cancelled) {
          setCandidates([]);
          setError(getApiErrorMessage(cause, "Impossibile caricare i calciatori liberi."));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken, activeRole, debouncedSearch, leagueId, order, reloadToken, visible]);

  async function confirm() {
    if (!target || !accessToken || !leagueId || buying) {
      return;
    }
    setBuying(true);
    setError(null);
    try {
      const purchase = await buyTradeReplacement(accessToken, leagueId, target.athleteId);
      setTarget(null);
      setReloadToken((value) => value + 1);
      onPurchased(purchase);
    } catch (cause) {
      // Es. il calciatore l'ha appena preso un'altra squadra: si torna all'elenco aggiornato.
      setError(getApiErrorMessage(cause, "Impossibile prendere il calciatore."));
      setTarget(null);
      setReloadToken((value) => value + 1);
    } finally {
      setBuying(false);
    }
  }

  if (!status) {
    return null;
  }
  const done = replacementDoneBanner(status);
  // Corsa Mercato del 25/11: nessun libero del ruolo alla portata dei crediti. L'elenco resta, grigio.
  const unaffordable = replacementUnaffordableNotice(status, activeRole);
  const closeOrBack = target ? () => setTarget(null) : onClose;

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={closeOrBack}>
      <Pressable style={shortfallStyles.backdrop} onPress={closeOrBack} accessibilityLabel={REPLACEMENT_LATER_LABEL}>
        <Pressable style={shortfallStyles.sheet} onPress={() => undefined} testID="replacement-sheet">
          <View style={shortfallStyles.grip} />
          <Text style={shortfallStyles.sheetTitle} accessibilityRole="header">
            {REPLACEMENT_SHEET_TITLE}
          </Text>
          {target && activeRole ? (
            <View style={styles.confirm} testID="replacement-confirm-step">
              <Text style={styles.confirmTitle}>{replacementConfirmTitle(target.name, target.marketValue)}</Text>
              <View style={styles.bill} testID="replacement-bill">
                {replacementCreditRows(status.balance, target.name, target.marketValue).map((row) => (
                  <View key={row.label} style={[styles.billRow, row.total && styles.billTotal]}>
                    <Text style={[styles.billLabel, row.total && styles.billStrong]}>{row.label}</Text>
                    <Text style={[styles.billValue, row.total && styles.billStrong]}>{row.value}</Text>
                  </View>
                ))}
              </View>
              <Text style={styles.muted} testID="replacement-confirm-note">
                {replacementConfirmNote(status, activeRole)}
              </Text>
              <View style={styles.actions}>
                <Pressable
                  style={[shortfallStyles.secondary, styles.action]}
                  onPress={() => setTarget(null)}
                  accessibilityRole="button"
                  testID="replacement-confirm-cancel"
                >
                  <Text style={shortfallStyles.secondaryLabel}>{REPLACEMENT_CANCEL_LABEL}</Text>
                </Pressable>
                <Pressable
                  style={[shortfallStyles.primary, styles.action, (buying || blocked) && shortfallStyles.disabled]}
                  disabled={buying || blocked}
                  onPress={() => void confirm()}
                  accessibilityRole="button"
                  testID="replacement-confirm"
                >
                  {buying ? (
                    <ActivityIndicator color={colors.onBrand} />
                  ) : (
                    <Text style={shortfallStyles.primaryLabel}>{REPLACEMENT_CONFIRM_LABEL}</Text>
                  )}
                </Pressable>
              </View>
            </View>
          ) : (
            <>
              {done ? (
                <View style={styles.done} testID="replacement-done">
                  <Text style={styles.doneLabel}>{`✓ ${done}`}</Text>
                </View>
              ) : null}
              {unaffordable ? <ReplacementUnaffordableBox text={unaffordable} /> : null}
              <Text style={styles.body} testID="replacement-intro">
                {replacementIntro(status.missingRoles)}
              </Text>
              {activeRole ? (
                <View style={styles.chips} testID="replacement-chips">
                  {replacementChips(status, activeRole).map((chip) => (
                    <View key={chip} style={styles.chip}>
                      <Text style={styles.chipLabel}>{chip}</Text>
                    </View>
                  ))}
                </View>
              ) : null}
              {status.blockedMessage ? (
                <Text style={styles.warning} testID="replacement-blocked">
                  {status.blockedMessage}
                </Text>
              ) : null}
              {roles.length > 1 ? (
                <View style={styles.chips} accessibilityRole="radiogroup">
                  {roles.map((item) => (
                    <Pressable
                      key={item}
                      style={[styles.roleButton, item === activeRole && styles.roleButtonActive]}
                      onPress={() => setRole(item)}
                      accessibilityRole="radio"
                      accessibilityState={{ selected: item === activeRole }}
                      testID={`replacement-role-${item}`}
                    >
                      <Text style={styles.chipLabel}>{roleSingularLabel(item)}</Text>
                    </Pressable>
                  ))}
                </View>
              ) : null}
              <TextInput
                style={styles.search}
                value={search}
                onChangeText={setSearch}
                placeholder={REPLACEMENT_SEARCH_PLACEHOLDER}
                accessibilityLabel="Cerca"
                autoCorrect={false}
                testID="replacement-search"
              />
              <View style={styles.chips} accessibilityRole="radiogroup" accessibilityLabel="Ordina per">
                {REPLACEMENT_ORDER_OPTIONS.map((option) => (
                  <Pressable
                    key={option.value}
                    style={[styles.roleButton, option.value === order && styles.roleButtonActive]}
                    onPress={() => setOrder(option.value)}
                    accessibilityRole="radio"
                    accessibilityState={{ selected: option.value === order }}
                    testID={`replacement-order-${option.value}`}
                  >
                    <Text style={styles.chipLabel}>{option.label}</Text>
                  </Pressable>
                ))}
              </View>
              {error ? (
                <Text style={styles.warning} testID="replacement-error">
                  {error}
                </Text>
              ) : null}
              <ScrollView style={styles.list} contentContainerStyle={styles.listContent} testID="replacement-list">
                {loading && candidates.length === 0 ? <ActivityIndicator color={colors.accent} /> : null}
                {!loading && candidates.length === 0 && !error ? (
                  <Text style={styles.muted}>{REPLACEMENT_EMPTY_LIST}</Text>
                ) : null}
                {candidates.map((candidate) => (
                  <View
                    key={candidate.athleteId}
                    style={[styles.row, !candidate.affordable && styles.rowDisabled]}
                    testID={`replacement-candidate-${candidate.athleteId}`}
                  >
                    <View style={styles.who}>
                      <Text style={styles.name} numberOfLines={1}>{`${candidate.role} · ${candidate.name}`}</Text>
                      <AthleteMarketTags
                        fields={candidate}
                        leading={
                          candidate.clubName ? <Text style={styles.club}>{candidate.clubName}</Text> : null
                        }
                      />
                      {!candidate.affordable ? (
                        <Text style={styles.expensive}>{REPLACEMENT_TOO_EXPENSIVE}</Text>
                      ) : null}
                    </View>
                    <Pressable
                      style={[shortfallStyles.primary, styles.take, (!candidate.affordable || blocked) && shortfallStyles.disabled]}
                      disabled={!candidate.affordable || blocked}
                      onPress={() => {
                        setError(null);
                        setTarget(candidate);
                      }}
                      accessibilityRole="button"
                      testID={`replacement-take-${candidate.athleteId}`}
                    >
                      <Text style={shortfallStyles.primaryLabel}>{replacementTakeLabel(candidate.marketValue)}</Text>
                    </Pressable>
                  </View>
                ))}
              </ScrollView>
              <View style={styles.later}>
                <Pressable
                  style={shortfallStyles.secondary}
                  onPress={onClose}
                  accessibilityRole="button"
                  testID="replacement-later"
                >
                  <Text style={shortfallStyles.secondaryLabel}>{REPLACEMENT_LATER_LABEL}</Text>
                </Pressable>
                <Text style={styles.muted}>{REPLACEMENT_LATER_NOTE}</Text>
              </View>
            </>
          )}
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = lazyStyles(() =>
  StyleSheet.create({
    body: { color: colors.foreground, lineHeight: 20 },
    muted: { color: colors.foregroundMuted, fontSize: typography.fontSize.sm, lineHeight: 18 },
    warning: { color: colors.warning, lineHeight: 20 },
    done: {
      padding: spacing.sm,
      borderRadius: radius.md,
      borderWidth: 1,
      borderColor: colors.success,
      backgroundColor: colors.backgroundSubtle,
    },
    doneLabel: { color: colors.success, fontWeight: typography.fontWeight.semibold },
    chips: { flexDirection: "row", flexWrap: "wrap", gap: spacing.xs },
    chip: {
      paddingHorizontal: 10,
      paddingVertical: 4,
      borderRadius: radius.pill,
      borderWidth: 1,
      borderColor: colors.borderStrong,
      backgroundColor: colors.background,
    },
    chipLabel: { color: colors.foreground, fontSize: 12, fontWeight: typography.fontWeight.semibold },
    roleButton: {
      minHeight: 36,
      justifyContent: "center",
      paddingHorizontal: spacing.sm,
      borderRadius: radius.pill,
      borderWidth: 1,
      borderColor: colors.border,
    },
    roleButtonActive: { borderColor: colors.brand, backgroundColor: colors.backgroundSubtle },
    search: {
      minHeight: 44,
      borderWidth: 1,
      borderColor: colors.border,
      borderRadius: radius.pill,
      paddingHorizontal: spacing.md,
      color: colors.foreground,
      backgroundColor: colors.background,
    },
    list: { flexGrow: 0, maxHeight: 360 },
    listContent: { gap: spacing.xs },
    row: {
      flexDirection: "row",
      alignItems: "center",
      gap: spacing.sm,
      padding: spacing.sm,
      borderRadius: radius.lg,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.background,
    },
    rowDisabled: { opacity: 0.6 },
    who: { flex: 1, minWidth: 0, gap: 4 },
    name: { color: colors.foreground, fontWeight: typography.fontWeight.semibold },
    club: { color: colors.foregroundMuted, fontSize: 12 },
    expensive: { color: colors.warning, fontSize: 12 },
    take: { minHeight: 40 },
    later: { gap: spacing.xs },
    confirm: { gap: spacing.sm },
    confirmTitle: { color: colors.foreground, fontSize: typography.fontSize.md, fontWeight: typography.fontWeight.bold },
    bill: {
      gap: spacing.xs,
      padding: spacing.md,
      borderRadius: radius.lg,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.background,
    },
    billRow: { flexDirection: "row", justifyContent: "space-between", gap: spacing.md },
    billTotal: { paddingTop: spacing.xs, borderTopWidth: 1, borderTopColor: colors.border },
    billLabel: { color: colors.foregroundMuted },
    billValue: { color: colors.foreground, fontVariant: ["tabular-nums"] },
    billStrong: { color: colors.foreground, fontWeight: typography.fontWeight.bold },
    actions: { flexDirection: "row", gap: spacing.sm },
    action: { flex: 1 },
  }),
);
