import type { AcceptedLeagueInvite } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useNavigation, useRoute, type RouteProp } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { acceptLeagueInvite } from "../api/leagues";
import { UiStatePanel } from "../components/UiStatePanel";
import { PageContainer } from "../layout/PageContainer";
import type { RootStackParamList } from "../navigation/types";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";

const { colors, spacing, typography, radius } = theme;

export function JoinLeagueScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const route = useRoute<RouteProp<RootStackParamList, "JoinLeague">>();
  const { can, accessToken, registerLeague, refreshMemberships } = useAuthSession();
  const token = route.params?.token?.trim() ?? "";
  const [code, setCode] = useState(route.params?.code ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AcceptedLeagueInvite | null>(null);

  async function goHome(accepted: AcceptedLeagueInvite) {
    registerLeague({
      id: accepted.leagueId,
      name: accepted.leagueName,
      role: "member",
    });
    try {
      await refreshMemberships();
    } catch {
      // L'ingresso è già riuscito; la lista si aggiornerà al prossimo focus.
    }
    navigation.replace("LeagueHome", { leagueId: accepted.leagueId });
  }

  if (!can(["league:view"])) {
    return (
      <PageContainer title="Entra in una lega" testID="screen-join-league">
        <UiStatePanel
          state="forbidden"
          title="Permessi insufficienti"
          message="Non puoi accettare inviti con questa sessione."
          testID="join-league-forbidden"
        />
      </PageContainer>
    );
  }

  async function onSubmit() {
    setError(null);
    if (!token && !code.trim()) {
      setError("Inserisci un codice invito.");
      return;
    }
    if (!accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setLoading(true);
    try {
      const accepted = await acceptLeagueInvite(
        accessToken,
        token ? { token } : { code: code.trim() },
      );
      setResult(accepted);
      await goHome(accepted);
    } catch (acceptError) {
      setError(getApiErrorMessage(acceptError, "Impossibile entrare nella lega."));
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <PageContainer title="Entra in una lega" testID="screen-join-league">
        <UiStatePanel
          state="loading"
          title="Verifica invito"
          message="Controllo validità e capienza della lega…"
          testID="join-league-loading"
        />
      </PageContainer>
    );
  }

  if (result) {
    return (
      <PageContainer title="Entra in una lega" testID="screen-join-league">
        <UiStatePanel
          state="success"
          title={result.alreadyMember ? "Sei già nella lega" : "Ingresso completato"}
          message={`Ora fai parte di ${result.leagueName}.`}
          testID="join-league-success"
        />
        <Pressable
          accessibilityRole="button"
          onPress={() => void goHome(result)}
          style={styles.primaryButton}
          testID="join-league-open-home"
        >
          <Text style={styles.primaryLabel}>Apri home lega</Text>
        </Pressable>
      </PageContainer>
    );
  }

  return (
    <PageContainer title="Entra in una lega" testID="screen-join-league">
      <Text style={styles.hint}>
        Ingresso solo su invito: usa il link ricevuto oppure inserisci il codice. Non esiste una
        ricerca pubblica delle leghe.
      </Text>
      {error ? (
        <UiStatePanel
          state="error"
          title="Ingresso non riuscito"
          message={error}
          testID="join-league-error"
        />
      ) : null}
      {token ? (
        <UiStatePanel
          state="success"
          title="Link invito pronto"
          message="Il token dal link è pronto per essere verificato."
          testID="join-league-token-ready"
        />
      ) : (
        <View>
          <Text style={styles.label}>Codice invito</Text>
          <TextInput
            value={code}
            onChangeText={setCode}
            autoCapitalize="characters"
            autoCorrect={false}
            placeholder="ABCDE-FGHIJ"
            placeholderTextColor={colors.foregroundMuted}
            style={styles.input}
            accessibilityLabel="Codice invito"
            testID="join-league-code"
          />
        </View>
      )}
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Entra nella lega"
        onPress={() => void onSubmit()}
        style={styles.primaryButton}
        testID="join-league-submit"
      >
        <Text style={styles.primaryLabel}>Entra nella lega</Text>
      </Pressable>
    </PageContainer>
  );
}

const styles = StyleSheet.create({
  hint: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    marginBottom: spacing.md,
  },
  label: {
    marginTop: spacing.md,
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
  },
  input: {
    marginTop: spacing.xs,
    minHeight: 44,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    color: colors.foreground,
    backgroundColor: colors.backgroundElevated,
  },
  primaryButton: {
    marginTop: spacing.md,
    minHeight: 44,
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  primaryLabel: {
    color: colors.accentContrast,
    fontSize: typography.fontSize.md,
    fontWeight: typography.fontWeight.semibold,
  },
});
