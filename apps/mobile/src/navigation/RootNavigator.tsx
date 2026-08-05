import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { useNavigation } from "@react-navigation/core";
import { AuthScreen } from "../screens/AuthScreen";
import { CreateLeagueScreen } from "../screens/CreateLeagueScreen";
import { JoinLeagueScreen } from "../screens/JoinLeagueScreen";
import { LeagueAdminScreen } from "../screens/LeagueAdminScreen";
import { ReceivedInvitesScreen } from "../screens/ReceivedInvitesScreen";
import { AdminNavigator } from "./AdminNavigator";
import { AppTabNavigator } from "./AppTabNavigator";
import type { RootStackParamList } from "./types";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { theme } from "@fantappero/ui/theme";
import { useDemoSession } from "../session/DemoSessionContext";
import type { DemoPersona } from "../session/demoSession";
import { PageContainer } from "../layout/PageContainer";
import { UiStatePanel } from "../components/UiStatePanel";
import { sceneBackgroundStyle } from "../theme/navigationTheme";

const Stack = createNativeStackNavigator<RootStackParamList>();
const { colors, spacing, typography, radius } = theme;

const PERSONAS: readonly { id: DemoPersona; label: string }[] = [
  { id: "member", label: "Membro" },
  { id: "admin", label: "Admin lega" },
  { id: "operator", label: "Operatore globale" },
];

function DevSettingsContent() {
  const { persona, setPersona, user } = useDemoSession();
  const navigation = useNavigation();

  return (
    <PageContainer title="Impostazioni demo" testID="screen-dev-settings">
      <UiStatePanel
        state="success"
        title="Sessione demo"
        message={`Persona attiva: ${user.displayName}. Cambia ruolo per verificare permessi e voci di navigazione.`}
        testID="dev-settings-intro"
      />
      <View accessibilityRole="radiogroup" accessibilityLabel="Persona demo">
        <Text style={styles.sectionLabel}>Persona</Text>
        <View style={styles.personaRow}>
          {PERSONAS.map((option) => {
            const selected = persona === option.id;
            return (
              <Pressable
                key={option.id}
                accessibilityRole="radio"
                accessibilityState={{ selected }}
                accessibilityLabel={option.label}
                onPress={() => setPersona(option.id)}
                style={[styles.personaChip, selected && styles.personaChipSelected]}
                testID={`persona-${option.id}`}
              >
                <Text
                  style={[styles.personaChipLabel, selected && styles.personaChipLabelSelected]}
                >
                  {option.label}
                </Text>
              </Pressable>
            );
          })}
        </View>
      </View>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Apri schermata autenticazione"
        onPress={() => navigation.navigate("Auth" as never)}
        style={styles.linkRow}
        testID="dev-open-auth"
      >
        <Text style={styles.linkText}>Schermata autenticazione</Text>
      </Pressable>
    </PageContainer>
  );
}

function DevSettingsScreenWrapper() {
  return (
    <ScrollView style={styles.devRoot} contentContainerStyle={styles.devContent}>
      <DevSettingsContent />
    </ScrollView>
  );
}

export function RootNavigator() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.backgroundElevated },
        headerTintColor: colors.foreground,
        headerTitleStyle: { color: colors.foreground },
        contentStyle: sceneBackgroundStyle,
      }}
    >
      <Stack.Screen name="MainTabs" component={AppTabNavigator} options={{ headerShown: false }} />
      <Stack.Screen name="Auth" component={AuthScreen} options={{ title: "Accedi", headerShown: false }} />
      <Stack.Screen name="CreateLeague" component={CreateLeagueScreen} options={{ title: "Crea lega" }} />
      <Stack.Screen name="LeagueAdmin" component={LeagueAdminScreen} options={{ title: "Admin lega" }} />
      <Stack.Screen name="JoinLeague" component={JoinLeagueScreen} options={{ title: "Entra in una lega" }} />
      <Stack.Screen
        name="ReceivedInvites"
        component={ReceivedInvitesScreen}
        options={{ title: "Inviti ricevuti" }}
      />
      <Stack.Screen name="AdminPanel" component={AdminNavigator} options={{ headerShown: false }} />
      <Stack.Screen name="DevSettings" component={DevSettingsScreenWrapper} options={{ title: "Demo" }} />
    </Stack.Navigator>
  );
}

const styles = StyleSheet.create({
  devRoot: {
    flex: 1,
    backgroundColor: colors.background,
  },
  devContent: {
    flexGrow: 1,
  },
  sectionLabel: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    fontWeight: typography.fontWeight.semibold,
    marginBottom: spacing.sm,
  },
  personaRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  personaChip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  personaChipSelected: {
    borderColor: colors.accent,
    backgroundColor: colors.backgroundElevated,
  },
  personaChipLabel: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
  },
  personaChipLabelSelected: {
    color: colors.accent,
    fontWeight: typography.fontWeight.semibold,
  },
  linkRow: {
    marginTop: spacing.lg,
    paddingVertical: spacing.sm,
  },
  linkText: {
    color: colors.accent,
    fontSize: typography.fontSize.md,
  },
});
