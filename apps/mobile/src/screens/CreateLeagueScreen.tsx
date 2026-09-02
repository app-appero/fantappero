import type { CompetitionSummary, LeagueDetail } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useNavigation } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useCallback, useMemo, useState } from "react";
import { Pressable, StyleSheet, Switch, Text, TextInput, View } from "react-native";
import { createLeague, fetchCompetitions } from "../api/leagues";
import { CoachDirectoryPanel } from "../components/CoachDirectoryPanel";
import { UiStatePanel } from "../components/UiStatePanel";
import { useScreenData } from "../hooks/useScreenData";
import { PageContainer } from "../layout/PageContainer";
import type { RootStackParamList } from "../navigation/types";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";

const { colors, spacing, typography, radius } = theme;

/** Anno di avvio stagione corrente (API: singolo intero; UI: YYYY-YYYY+1). */
export function currentSeasonYear(now = new Date()): number {
  return now.getFullYear();
}

export function formatSeasonLabel(seasonYear: number): string {
  return `${seasonYear}-${seasonYear + 1}`;
}

/** Creazione lega privata in bozza (EP03-01). */
export function CreateLeagueScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { can, accessToken, registerLeague, refreshMemberships } = useAuthSession();
  const seasonYear = useMemo(() => currentSeasonYear(), []);
  const seasonLabel = useMemo(() => formatSeasonLabel(seasonYear), [seasonYear]);

  const [competitions, setCompetitions] = useState<CompetitionSummary[]>([]);
  const [loadingCatalog, setLoadingCatalog] = useState(true);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [createdLeague, setCreatedLeague] = useState<LeagueDetail | null>(null);
  const [directoryCompleted, setDirectoryCompleted] = useState(false);

  const selectedCount = competitions.filter((row) => selected[row.id]).length;
  const allSelected = competitions.length > 0 && selectedCount === competitions.length;

  const loadCatalog = useCallback(
    async (options?: { silent?: boolean }) => {
      if (!accessToken) {
        setCatalogError("Sessione non disponibile. Accedi di nuovo.");
        setLoadingCatalog(false);
        return;
      }
      if (!options?.silent) {
        setLoadingCatalog(true);
      }
      setCatalogError(null);
      try {
        setCompetitions(await fetchCompetitions(accessToken));
      } catch (error) {
        setCatalogError(getApiErrorMessage(error, "Impossibile caricare i campionati."));
      } finally {
        setLoadingCatalog(false);
      }
    },
    [accessToken],
  );

  const { refreshing, onRefresh } = useScreenData(loadCatalog);

  if (!can(["league:view"])) {
    return (
      <PageContainer title="Crea lega" testID="screen-create-league">
        <UiStatePanel
          state="forbidden"
          title="Accesso negato"
          message="Non hai i permessi per creare una lega."
          testID="create-league-forbidden"
        />
      </PageContainer>
    );
  }

  function toggleCompetition(id: string) {
    setSelected((current) => ({ ...current, [id]: !current[id] }));
  }

  function toggleSelectAll() {
    if (allSelected) {
      setSelected({});
      return;
    }
    const next: Record<string, boolean> = {};
    for (const row of competitions) {
      next[row.id] = true;
    }
    setSelected(next);
  }

  async function handleSubmit() {
    setFormError(null);
    if (!name.trim()) {
      setFormError("Inserisci un nome per la lega.");
      return;
    }
    const selectedIds = competitions.filter((row) => selected[row.id]).map((row) => row.id);
    if (selectedIds.length < 3) {
      setFormError("Seleziona almeno 3 campionati.");
      return;
    }

    if (!accessToken) {
      setFormError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }

    setSubmitting(true);
    try {
      const created = await createLeague(accessToken, {
        name: name.trim(),
        seasonYear,
        competitionIds: selectedIds,
      });
      registerLeague({
        id: created.id,
        name: created.name,
        role: created.viewerRole === "league_admin" ? "league_admin" : "member",
        state: created.state,
      });
      try {
        await refreshMemberships();
      } catch {
        // Creazione già riuscita; registerLeague ha aggiornato lo stato locale.
      }
      setCreatedLeague(created);
    } catch (error) {
      setFormError(getApiErrorMessage(error, "Impossibile creare la lega."));
    } finally {
      setSubmitting(false);
    }
  }

  if (createdLeague) {
    return (
      <PageContainer title="Crea lega · Fase 2" testID="screen-create-league-directory">
        <UiStatePanel
          state="success"
          title={directoryCompleted ? "Configurazione completata" : "Lega creata"}
          message={
            directoryCompleted
              ? "Puoi continuare dall'elenco leghe o dall'amministrazione."
              : `"${createdLeague.name}" salvata in bozza. Sei amministratore.`
          }
          testID={
            directoryCompleted ? "create-league-directory-complete" : "create-league-phase-2"
          }
        />
        {!directoryCompleted ? (
          <>
            <CoachDirectoryPanel
              leagueId={createdLeague.id}
              memberCount={1}
              capacity={createdLeague.rules?.participantCount ?? 8}
              testIDPrefix="create-league-directory"
            />
            <Pressable
              accessibilityRole="button"
              onPress={() => setDirectoryCompleted(true)}
              style={styles.secondaryButton}
              testID="create-league-directory-skip"
            >
              <Text style={styles.secondaryButtonLabel}>Salta e termina</Text>
            </Pressable>
          </>
        ) : (
          <View style={styles.footerActions}>
            <Pressable
              accessibilityRole="button"
              onPress={() => navigation.navigate("LeagueAdmin", { leagueId: createdLeague.id })}
              style={styles.primaryButton}
              testID="create-league-open-admin"
            >
              <Text style={styles.primaryButtonLabel}>Apri amministrazione</Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              onPress={() => navigation.navigate("LeagueHome", { leagueId: createdLeague.id })}
              style={styles.secondaryButton}
              testID="create-league-back-list"
            >
              <Text style={styles.secondaryButtonLabel}>Vai alla home lega</Text>
            </Pressable>
          </View>
        )}
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title="Crea lega"
      testID="screen-create-league"
      refreshing={refreshing}
      onRefresh={onRefresh}
    >
      {loadingCatalog ? (
        <UiStatePanel
          state="loading"
          title="Caricamento campionati"
          message="Recupero del catalogo in corso…"
          testID="create-league-catalog-loading"
        />
      ) : null}
      {catalogError ? (
        <UiStatePanel
          state="error"
          title="Catalogo non disponibile"
          message={catalogError}
          testID="create-league-catalog-error"
        />
      ) : null}
      {formError ? (
        <UiStatePanel state="error" title="Errore" message={formError} testID="create-league-error" />
      ) : null}

      {!loadingCatalog && !catalogError ? (
        <View style={styles.section} testID="create-league-form">
          <Text style={styles.label}>Nome lega</Text>
          <TextInput
            value={name}
            onChangeText={setName}
            style={styles.input}
            placeholder="Es. Lega degli amici"
            placeholderTextColor={colors.foregroundMuted}
            accessibilityLabel="Nome lega"
            testID="create-league-name"
          />

          <Text style={styles.label}>Stagione</Text>
          <View style={styles.seasonReadonly} testID="create-league-season">
            <Text style={styles.seasonReadonlyLabel}>{seasonLabel}</Text>
            <Text style={styles.seasonHint}>Stagione sportiva corrente</Text>
          </View>

          <View style={styles.competitionHeader}>
            <Text style={styles.label}>Campionati (minimo 3)</Text>
            <Pressable
              accessibilityRole="button"
              onPress={toggleSelectAll}
              testID="create-league-select-all"
              hitSlop={8}
            >
              <Text style={styles.selectAllLabel}>
                {allSelected ? "Deseleziona tutto" : "Seleziona tutto"}
              </Text>
            </Pressable>
          </View>
          <Text style={styles.competitionCount}>
            {selectedCount} di {competitions.length} selezionati
          </Text>
          {competitions.map((competition) => {
            const isSelected = Boolean(selected[competition.id]);
            return (
              <Pressable
                key={competition.id}
                accessibilityRole="checkbox"
                accessibilityState={{ checked: isSelected }}
                onPress={() => toggleCompetition(competition.id)}
                style={[styles.competitionRow, isSelected && styles.competitionRowSelected]}
                testID={`create-league-competition-${competition.id}`}
              >
                <Switch
                  value={isSelected}
                  onValueChange={() => toggleCompetition(competition.id)}
                  trackColor={{ false: colors.border, true: colors.accent }}
                  pointerEvents="none"
                />
                <View style={styles.competitionText}>
                  <Text style={styles.competitionLabel}>{competition.name}</Text>
                  <Text style={styles.competitionCountry}>{competition.country}</Text>
                </View>
              </Pressable>
            );
          })}

          <Pressable
            accessibilityRole="button"
            disabled={submitting}
            onPress={() => void handleSubmit()}
            style={[styles.primaryButton, submitting && styles.disabled]}
            testID="create-league-submit"
          >
            <Text style={styles.primaryButtonLabel}>
              {submitting ? "Creazione…" : "Crea lega privata"}
            </Text>
          </Pressable>
        </View>
      ) : null}
    </PageContainer>
  );
}

const styles = StyleSheet.create({
  section: {
    gap: spacing.sm,
  },
  label: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
    marginTop: spacing.sm,
  },
  input: {
    minHeight: 44,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    color: colors.foreground,
    backgroundColor: colors.backgroundElevated,
  },
  seasonReadonly: {
    minHeight: 44,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.backgroundElevated,
    gap: 2,
  },
  seasonReadonlyLabel: {
    color: colors.foreground,
    fontSize: typography.fontSize.md,
    fontWeight: typography.fontWeight.semibold,
  },
  seasonHint: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.xs,
  },
  competitionHeader: {
    marginTop: spacing.sm,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  selectAllLabel: {
    color: colors.accent,
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
  },
  competitionCount: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.xs,
    marginBottom: spacing.xs,
  },
  competitionRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.xs,
    minHeight: 48,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.backgroundElevated,
  },
  competitionRowSelected: {
    borderColor: colors.accent,
  },
  competitionText: {
    flexShrink: 1,
    gap: 2,
  },
  competitionLabel: {
    color: colors.foreground,
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
  },
  competitionCountry: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.xs,
  },
  primaryButton: {
    marginTop: spacing.md,
    minHeight: 44,
    backgroundColor: colors.accent,
    borderRadius: radius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
    justifyContent: "center",
  },
  primaryButtonLabel: {
    color: colors.accentContrast,
    fontWeight: typography.fontWeight.semibold,
    fontSize: typography.fontSize.md,
  },
  secondaryButton: {
    minHeight: 44,
    borderWidth: 1,
    borderColor: colors.accent,
    borderRadius: radius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
    justifyContent: "center",
  },
  secondaryButtonLabel: {
    color: colors.accent,
    fontWeight: typography.fontWeight.semibold,
  },
  footerActions: {
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  disabled: {
    opacity: 0.6,
  },
});
