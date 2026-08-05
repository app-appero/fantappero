import { theme } from "@fantappero/ui/theme";
import { useRoute, type RouteProp } from "@react-navigation/core";
import { useMemo, useState } from "react";
import { Pressable, StyleSheet, Switch, Text, TextInput, View } from "react-native";
import { CoachDirectoryPanel } from "../components/CoachDirectoryPanel";
import { PageContainer } from "../layout/PageContainer";
import { UiStatePanel } from "../components/UiStatePanel";
import type { RootStackParamList } from "../navigation/types";
import { useDemoSession } from "../session/DemoSessionContext";
import { resolveDirectoryState } from "./directoryDemo";

const { colors, spacing, typography, radius } = theme;

const DEMO_COMPETITIONS = [
  { id: "demo-39", name: "Premier League", country: "England" },
  { id: "demo-140", name: "La Liga", country: "Spain" },
  { id: "demo-135", name: "Serie A", country: "Italy" },
  { id: "demo-78", name: "Bundesliga", country: "Germany" },
  { id: "demo-61", name: "Ligue 1", country: "France" },
];

/** Creazione lega privata in bozza — flusso demo con validazioni (EP03-01). */
export function CreateLeagueScreen() {
  const { can } = useDemoSession();
  const route = useRoute<RouteProp<RootStackParamList, "CreateLeague">>();
  const seasonOptions = useMemo(() => {
    const currentYear = new Date().getFullYear();
    return [currentYear - 1, currentYear, currentYear + 1];
  }, []);

  const [name, setName] = useState("");
  const [seasonYear, setSeasonYear] = useState(String(new Date().getFullYear()));
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [phase, setPhase] = useState<1 | 2>(1);
  const [directoryCompleted, setDirectoryCompleted] = useState(false);

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

  function handleSubmit() {
    setFormError(null);
    setSuccessMessage(null);

    if (!name.trim()) {
      setFormError("Inserisci un nome per la lega.");
      return;
    }

    const selectedCount = DEMO_COMPETITIONS.filter((row) => selected[row.id]).length;
    if (selectedCount < 3) {
      setFormError("Seleziona almeno 3 campionati.");
      return;
    }

    setSuccessMessage(`"${name.trim()}" salvata in bozza (demo). Sei amministratore.`);
    setPhase(2);
  }

  if (phase === 2) {
    const directoryState = resolveDirectoryState(true, route.params?.directory);
    return (
      <PageContainer title="Crea lega · Fase 2" testID="screen-create-league-directory">
        <UiStatePanel
          state="success"
          title={directoryCompleted ? "Configurazione demo completata" : "Lega creata"}
          message={
            directoryCompleted
              ? "La fase directory è stata chiusa. Gli inviti restano solo nella sessione locale."
              : `${successMessage} Ora puoi invitare facoltativamente dalla directory.`
          }
          testID={
            directoryCompleted ? "create-league-directory-complete" : "create-league-phase-2"
          }
        />
        {!directoryCompleted ? (
          <>
            <CoachDirectoryPanel
              state={directoryState}
              memberCount={1}
              capacity={8}
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
        ) : null}
      </PageContainer>
    );
  }

  return (
    <PageContainer title="Crea lega" testID="screen-create-league">
      {successMessage ? (
        <UiStatePanel
          state="success"
          title="Lega creata"
          message={successMessage}
          testID="create-league-success"
        />
      ) : null}

      {formError ? (
        <UiStatePanel state="error" title="Errore" message={formError} testID="create-league-error" />
      ) : null}

      <View style={styles.section} testID="create-league-form">
        <Text style={styles.label}>Nome lega</Text>
        <TextInput
          value={name}
          onChangeText={setName}
          style={styles.input}
          placeholder="Es. Lega degli amici"
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
        {DEMO_COMPETITIONS.map((competition) => (
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
          onPress={handleSubmit}
          style={styles.primaryButton}
          testID="create-league-submit"
        >
          <Text style={styles.primaryButtonLabel}>Crea lega privata</Text>
        </Pressable>
      </View>
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
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
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
    backgroundColor: colors.accent,
    borderRadius: radius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
  },
  primaryButtonLabel: {
    color: colors.background,
    fontWeight: typography.fontWeight.semibold,
    fontSize: typography.fontSize.md,
  },
  secondaryButton: {
    borderWidth: 1,
    borderColor: colors.accent,
    borderRadius: radius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
  },
  secondaryButtonLabel: {
    color: colors.accent,
    fontWeight: typography.fontWeight.semibold,
  },
});
