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

/** Creazione lega privata in bozza (EP03-01). */
export function CreateLeagueScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { can, accessToken, registerLeague, refreshMemberships } = useAuthSession();
  const seasonOptions = useMemo(() => {
    const currentYear = new Date().getFullYear();
    return [currentYear - 1, currentYear, currentYear + 1];
  }, []);

  const [competitions, setCompetitions] = useState<CompetitionSummary[]>([]);
  const [loadingCatalog, setLoadingCatalog] = useState(true);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [seasonYear, setSeasonYear] = useState(String(new Date().getFullYear()));
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [createdLeague, setCreatedLeague] = useState<LeagueDetail | null>(null);
  const [directoryCompleted, setDirectoryCompleted] = useState(false);

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
        seasonYear: Number(seasonYear),
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
              onPress={() => navigation.navigate("MainTabs", { screen: "Leagues" } as never)}
              style={styles.secondaryButton}
              testID="create-league-back-list"
            >
              <Text style={styles.secondaryButtonLabel}>Torna alle leghe</Text>
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
          <View style={styles.seasonRow}>
            {seasonOptions.map((year) => {
              const selectedSeason = seasonYear === String(year);
              return (
                <Pressable
                  key={year}
                  accessibilityRole="button"
                  onPress={() => setSeasonYear(String(year))}
                  style={[styles.seasonChip, selectedSeason && styles.seasonChipSelected]}
                  testID={`create-league-season-${year}`}
                >
                  <Text style={[styles.seasonLabel, selectedSeason && styles.seasonLabelSelected]}>
                    {year}
                  </Text>
                </Pressable>
              );
            })}
          </View>

          <Text style={styles.label}>Campionati (minimo 3)</Text>
          {competitions.map((competition) => (
            <View key={competition.id} style={styles.competitionRow}>
              <Switch
                value={Boolean(selected[competition.id])}
                onValueChange={() => toggleCompetition(competition.id)}
                testID={`create-league-competition-${competition.id}`}
              />
              <Text style={styles.competitionLabel}>
                {competition.name} ({competition.country})
              </Text>
            </View>
          ))}

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
  seasonRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  seasonChip: {
    minHeight: 44,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    justifyContent: "center",
  },
  seasonChipSelected: {
    borderColor: colors.accent,
    backgroundColor: colors.backgroundElevated,
  },
  seasonLabel: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  seasonLabelSelected: {
    color: colors.accent,
    fontWeight: typography.fontWeight.semibold,
  },
  competitionRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.xs,
  },
  competitionLabel: {
    color: colors.foreground,
    fontSize: typography.fontSize.sm,
    flexShrink: 1,
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
