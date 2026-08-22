import type { AdminOverview } from "@fantappero/contracts";
import { useNavigation } from "@react-navigation/core";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useCallback, useState } from "react";
import { Pressable, Text, View } from "react-native";
import { fetchAdminOverview } from "../../api/admin";
import { ApiError } from "../../api/client";
import { adminUiStyles as styles } from "../../admin/adminUiStyles";
import { UiStatePanel } from "../../components/UiStatePanel";
import { useScreenData } from "../../hooks/useScreenData";
import { PageContainer } from "../../layout/PageContainer";
import type { AdminStackParamList } from "../../navigation/types";
import { getApiErrorMessage, useAuthSession } from "../../session/DemoSessionContext";

/** Panoramica operatore — mobile port of `apps/web/src/pages/AdminDashboardPage.tsx` (EP11-04a). */
export function AdminDashboardScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<AdminStackParamList>>();
  const { accessToken } = useAuthSession();

  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    if (!accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      setOverview(null);
      setLoading(false);
      return;
    }
    try {
      setOverview(await fetchAdminOverview(accessToken));
    } catch (loadError) {
      if (loadError instanceof ApiError && loadError.status === 403) {
        setError("Non hai i permessi per consultare il pannello operatore.");
      } else {
        setError(getApiErrorMessage(loadError, "Impossibile caricare il pannello operatore."));
      }
      setOverview(null);
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  const { refreshing, onRefresh } = useScreenData(load);

  return (
    <PageContainer
      title="Pannello operatore"
      testID="screen-admin-dashboard"
      refreshing={refreshing}
      onRefresh={onRefresh}
    >
      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento"
          message="Recupero i dati del pannello operatore…"
          testID="admin-dashboard-loading"
        />
      ) : null}
      {!loading && error ? (
        <UiStatePanel
          state={error.includes("permessi") ? "forbidden" : "error"}
          title="Pannello non disponibile"
          message={error}
          testID="admin-dashboard-error"
        />
      ) : null}
      {!loading && !error && overview ? (
        <View style={styles.section} testID="admin-dashboard-success">
          <Text style={styles.sectionTitle}>Identità operatore</Text>
          <Text style={styles.name} testID="admin-overview-name">
            {overview.operatorDisplayName}
          </Text>
          <Text style={styles.meta}>
            Ambiente: <Text testID="admin-overview-environment">{overview.environment}</Text>
          </Text>
          <Text style={styles.sectionTitle}>Conteggi piattaforma</Text>
          <Text style={styles.meta}>Utenti registrati: {overview.usersCount}</Text>
          <Text style={styles.meta}>Operatori: {overview.operatorsCount}</Text>
          <Text style={styles.meta}>Leghe: {overview.leaguesCount}</Text>
        </View>
      ) : null}
      {!loading && !error && !overview ? (
        <UiStatePanel
          state="empty"
          title="Nessun dato disponibile"
          message="Non è stato possibile calcolare i conteggi piattaforma."
          testID="admin-dashboard-empty"
        />
      ) : null}

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Sezioni</Text>
        <Pressable
          style={styles.linkCard}
          onPress={() => navigation.navigate("AdminLeagues")}
          testID="admin-dashboard-link-leagues"
        >
          <Text style={styles.linkCardTitle}>Leghe globali</Text>
          <Text style={styles.linkCardHint}>Consulta tutte le leghe della piattaforma.</Text>
        </Pressable>
        <Pressable
          style={styles.linkCard}
          onPress={() => navigation.navigate("AdminUsers")}
          testID="admin-dashboard-link-users"
        >
          <Text style={styles.linkCardTitle}>Utenti</Text>
          <Text style={styles.linkCardHint}>Cerca utenti, promuovi o revoca operatori.</Text>
        </Pressable>
        <Pressable
          style={styles.linkCard}
          onPress={() => navigation.navigate("AdminListone")}
          testID="admin-dashboard-link-listone"
        >
          <Text style={styles.linkCardTitle}>Listone</Text>
          <Text style={styles.linkCardHint}>
            Consulta e aggiorna il listone ufficiale dal provider.
          </Text>
        </Pressable>
      </View>
    </PageContainer>
  );
}
