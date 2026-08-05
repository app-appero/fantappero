import type { RouteProp } from "@react-navigation/core";
import { useRoute } from "@react-navigation/core";
import type { LeagueState } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { CoachDirectoryPanel } from "../components/CoachDirectoryPanel";
import { UiStatePanel } from "../components/UiStatePanel";
import { PageContainer } from "../layout/PageContainer";
import type { RootStackParamList } from "../navigation/types";
import { useDemoSession } from "../session/DemoSessionContext";
import { resolveDirectoryState } from "./directoryDemo";
import {
  resolveAdminInviteState,
  resolveLeagueCalendarState,
  resolveLeagueSeasonState,
} from "./inviteDemo";

const { colors, spacing, typography, radius } = theme;

type DemoMember = {
  id: string;
  name: string;
  role: "league_admin" | "member";
};

const INITIAL_MEMBERS: DemoMember[] = [
  { id: "demo-admin", name: "Marco", role: "league_admin" },
  { id: "demo-member-1", name: "Giulia", role: "member" },
  { id: "demo-member-2", name: "Luca", role: "member" },
];

export function LeagueAdminScreen() {
  const { can } = useDemoSession();
  const route = useRoute<RouteProp<RootStackParamList, "LeagueAdmin">>();
  const state = resolveAdminInviteState(can(["league:admin"]), route.params?.stato);
  const seasonState = resolveLeagueSeasonState(
    can(["league:admin"]),
    route.params?.stagione,
  );
  const calendarState = resolveLeagueCalendarState(
    can(["league:admin"]),
    route.params?.calendario,
  );
  const directoryState = resolveDirectoryState(
    can(["league:admin"]),
    route.params?.directory,
  );
  const [inviteCreated, setInviteCreated] = useState(false);
  const [revoked, setRevoked] = useState(false);
  const [members, setMembers] = useState(INITIAL_MEMBERS);
  const [memberSuccess, setMemberSuccess] = useState<string | null>(null);
  const [leagueState, setLeagueState] = useState<LeagueState>("draft");
  const [calendarGenerated, setCalendarGenerated] = useState(false);
  const [calendarConfirmed, setCalendarConfirmed] = useState(false);
  const [calendarSuccess, setCalendarSuccess] = useState<string | null>(null);

  if (state === "forbidden") {
    return (
      <PageContainer title="Amministrazione lega" testID="screen-league-admin">
        <UiStatePanel
          state="forbidden"
          title="Permessi insufficienti"
          message="Solo l'amministratore della lega può gestire partecipanti e inviti."
          testID="league-admin-forbidden"
        />
      </PageContainer>
    );
  }

  if (state !== "success") {
    const copy = {
      loading: {
        title: "Caricamento amministrazione",
        message: "Recupero della configurazione demo…",
      },
      empty: {
        title: "Nessun partecipante",
        message: "Non risultano partecipanti iscritti alla lega.",
      },
      error: {
        title: "Amministrazione non disponibile",
        message: "Non è stato possibile caricare partecipanti e inviti (demo).",
      },
    }[state];
    return (
      <PageContainer title="Amministrazione lega" testID="screen-league-admin">
        <UiStatePanel
          state={state}
          title={copy.title}
          message={copy.message}
          testID={`league-admin-${state}`}
        />
        <View testID={`league-members-${state}`} />
      </PageContainer>
    );
  }

  return (
    <PageContainer title="Amministrazione lega" testID="screen-league-admin">
      <Text style={styles.heading}>Partecipanti iscritti</Text>
      <Text style={styles.body}>
        Trasferisci il ruolo admin o rimuovi un partecipante prima dell’avvio.
      </Text>
      <View style={styles.memberList} testID="league-members-list">
        {members.map((member) => (
          <View key={member.id} style={styles.inviteRow}>
            <View>
              <Text style={styles.inviteTitle}>{member.name}</Text>
              <Text style={styles.body}>
                {member.role === "league_admin" ? "Amministratore" : "Partecipante"}
              </Text>
            </View>
            {member.role === "member" ? (
              <View style={styles.row}>
                <Pressable
                  accessibilityRole="button"
                  onPress={() => {
                    setMembers((current) =>
                      current.map((row) => ({
                        ...row,
                        role: row.id === member.id ? "league_admin" : "member",
                      })),
                    );
                    setMemberSuccess(`Ruolo admin trasferito a ${member.name}.`);
                  }}
                  style={styles.secondaryButton}
                  testID={`league-member-transfer-${member.id}`}
                >
                  <Text style={styles.secondaryLabel}>Trasferisci admin</Text>
                </Pressable>
                <Pressable
                  accessibilityRole="button"
                  onPress={() => {
                    setMembers((current) => current.filter((row) => row.id !== member.id));
                    setMemberSuccess(`${member.name} è stato rimosso dalla lega.`);
                  }}
                  style={styles.dangerButton}
                  testID={`league-member-remove-${member.id}`}
                >
                  <Text style={styles.dangerLabel}>Rimuovi</Text>
                </Pressable>
              </View>
            ) : null}
          </View>
        ))}
      </View>
      {memberSuccess ? (
        <UiStatePanel
          state="success"
          title="Partecipanti aggiornati"
          message={memberSuccess}
          testID="league-members-success"
        />
      ) : null}

      <Text style={styles.heading}>Calendario scontri diretti</Text>
      {calendarState !== "success" ? (
        <UiStatePanel
          state={calendarState}
          title={
            calendarState === "loading"
              ? "Caricamento calendario"
              : calendarState === "empty"
                ? "Nessun calendario"
                : calendarState === "forbidden"
                  ? "Permessi insufficienti"
                  : "Calendario non disponibile"
          }
          message={
            calendarState === "loading"
              ? "Recupero degli scontri diretti in corso…"
              : calendarState === "empty"
                ? "Genera l'anteprima quando i partecipanti sono completi."
                : calendarState === "forbidden"
                  ? "Solo l'amministratore della lega può generare il calendario."
                  : "Non è stato possibile caricare il calendario (demo)."
          }
          testID={`league-calendar-${calendarState}`}
        />
      ) : (
        <View style={styles.section} testID="league-calendar-panel">
          <Text style={styles.body}>
            {calendarConfirmed
              ? "Calendario confermato: ogni partecipante incontra gli altri una volta."
              : calendarGenerated
                ? "Anteprima pronta: 6 incontri su 3 turni."
                : "Genera un girone di andata bilanciato prima dell'avvio stagione."}
          </Text>
          <Pressable
            accessibilityRole="button"
            onPress={() => {
              setCalendarGenerated(true);
              setCalendarConfirmed(false);
              setCalendarSuccess("Anteprima calendario generata.");
            }}
            style={styles.primaryButton}
            testID="league-calendar-generate"
          >
            <Text style={styles.primaryLabel}>Genera anteprima</Text>
          </Pressable>
          {calendarGenerated ? (
            <Pressable
              accessibilityRole="button"
              onPress={() => {
                setCalendarConfirmed(true);
                setCalendarSuccess("Calendario confermato.");
              }}
              style={styles.secondaryButton}
              testID="league-calendar-confirm"
            >
              <Text style={styles.secondaryLabel}>Conferma calendario</Text>
            </Pressable>
          ) : null}
          {calendarSuccess ? (
            <UiStatePanel
              state="success"
              title="Calendario aggiornato"
              message={calendarSuccess}
              testID="league-calendar-success"
            />
          ) : null}
        </View>
      )}

      <Text style={styles.heading}>Stato e avvio stagione</Text>
      {seasonState !== "success" ? (
        <UiStatePanel
          state={seasonState}
          title={
            seasonState === "loading"
              ? "Caricamento stato stagione"
              : seasonState === "empty"
                ? "Nessuna transizione disponibile"
                : "Stato stagione non disponibile"
          }
          message={
            seasonState === "loading"
              ? "Verifica dei prerequisiti in corso…"
              : seasonState === "empty"
                ? "La lega non ha azioni di stagione disponibili."
                : "Non è stato possibile verificare i prerequisiti (demo)."
          }
          testID={`league-season-${seasonState}`}
        />
      ) : (
        <View style={styles.section} testID="league-season-panel">
          <Text style={styles.body}>
            Stato corrente: {leagueState === "draft" ? "Bozza" : "Configurazione"}
          </Text>
          {leagueState === "draft" ? (
            <Pressable
              accessibilityRole="button"
              onPress={() => setLeagueState("configuring")}
              style={styles.primaryButton}
              testID="league-season-transition-configuring"
            >
              <Text style={styles.primaryLabel}>Apri configurazione</Text>
            </Pressable>
          ) : (
            <UiStatePanel
              state="empty"
              title="Asta non ancora disponibile"
              message={`Servono 8 partecipanti; al momento sono iscritti ${members.length}.`}
              testID="league-season-blockers"
            />
          )}
        </View>
      )}

      <Text style={styles.heading}>Directory fantallenatori</Text>
      <Text style={styles.body}>
        Consulta i profili che hanno scelto di rendersi disponibili e simula un invito nominativo.
      </Text>
      <CoachDirectoryPanel
        state={directoryState}
        memberCount={members.length}
        capacity={8}
        testIDPrefix="league-admin-directory"
      />

      <Text style={styles.heading}>Inviti tramite link o codice</Text>
      <Text style={styles.body}>
        Genera link e codice validi per 7 giorni, fino a revoca o capienza.
      </Text>
      <Pressable
        accessibilityRole="button"
        onPress={() => {
          setInviteCreated(true);
          setRevoked(false);
        }}
        style={styles.primaryButton}
        testID="league-invite-create"
      >
        <Text style={styles.primaryLabel}>Genera invito</Text>
      </Pressable>

      {inviteCreated ? (
        <View style={styles.section}>
          <UiStatePanel
            state="success"
            title="Invito generato"
            message="Codice FANTA-2026X. Copialo ora: non sarà mostrato di nuovo."
            testID="league-invite-created"
          />
          <View style={styles.row}>
            <Pressable style={styles.secondaryButton} accessibilityRole="button">
              <Text style={styles.secondaryLabel}>Copia link</Text>
            </Pressable>
            <Pressable style={styles.secondaryButton} accessibilityRole="button">
              <Text style={styles.secondaryLabel}>Copia codice</Text>
            </Pressable>
          </View>
        </View>
      ) : null}

      <View style={styles.inviteRow}>
        <View>
          <Text style={styles.inviteTitle}>{revoked ? "Revocato" : "Attivo"}</Text>
          <Text style={styles.body}>Scade il 10 agosto 2026 alle 10:00</Text>
        </View>
        {!revoked ? (
          <Pressable
            accessibilityRole="button"
            onPress={() => setRevoked(true)}
            style={styles.dangerButton}
            testID="league-invite-revoke"
          >
            <Text style={styles.dangerLabel}>Revoca</Text>
          </Pressable>
        ) : null}
      </View>
    </PageContainer>
  );
}

const styles = StyleSheet.create({
  heading: {
    color: colors.foreground,
    fontSize: typography.fontSize.xl,
    fontWeight: typography.fontWeight.semibold,
  },
  body: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  section: {
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  row: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  memberList: {
    gap: spacing.sm,
    marginBottom: spacing.xl,
  },
  primaryButton: {
    marginTop: spacing.md,
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.accent,
    alignItems: "center",
  },
  primaryLabel: {
    color: colors.background,
    fontWeight: typography.fontWeight.semibold,
  },
  secondaryButton: {
    padding: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
  },
  secondaryLabel: {
    color: colors.accent,
    fontWeight: typography.fontWeight.semibold,
  },
  inviteRow: {
    marginTop: spacing.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: spacing.sm,
  },
  inviteTitle: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.semibold,
  },
  dangerButton: {
    padding: spacing.sm,
    borderWidth: 1,
    borderColor: colors.danger,
    borderRadius: radius.md,
  },
  dangerLabel: {
    color: colors.danger,
    fontWeight: typography.fontWeight.semibold,
  },
});
