import { theme } from "@fantappero/ui/theme";
import { useCallback, useState } from "react";
import { StyleSheet, View } from "react-native";
import { CoachDirectoryPanel } from "../components/CoachDirectoryPanel";
import { UiStatePanel } from "../components/UiStatePanel";
import { PageContainer } from "../layout/PageContainer";
import { useAuthSession } from "../session/DemoSessionContext";

const { spacing } = theme;

/** Directory fantallenatori dedicata — allineata a web /fantallenatori. */
export function ManagerDirectoryScreen() {
  const { can, activeLeagueId } = useAuthSession();
  const [reloadToken, setReloadToken] = useState(0);
  const [refreshing, setRefreshing] = useState(false);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    setReloadToken((current) => current + 1);
  }, []);

  const onReloadSettled = useCallback(() => {
    setRefreshing(false);
  }, []);

  if (!can(["league:admin"])) {
    return (
      <PageContainer title="Fantallenatori" testID="screen-manager-directory">
        <UiStatePanel
          state="forbidden"
          title="Permessi insufficienti"
          message="Solo l'amministratore della lega può consultare la directory."
          testID="manager-directory-forbidden"
        />
      </PageContainer>
    );
  }

  if (!activeLeagueId) {
    return (
      <PageContainer title="Fantallenatori" testID="screen-manager-directory">
        <UiStatePanel
          state="empty"
          title="Nessuna lega selezionata"
          message="Seleziona una lega amministrata per consultare la directory."
          testID="manager-directory-no-league"
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title="Fantallenatori"
      testID="screen-manager-directory"
      refreshing={refreshing}
      onRefresh={onRefresh}
    >
      <View style={styles.body}>
        <CoachDirectoryPanel
          leagueId={activeLeagueId}
          memberCount={0}
          capacity={10}
          testIDPrefix="manager-directory"
          reloadToken={reloadToken}
          onReloadSettled={onReloadSettled}
        />
      </View>
    </PageContainer>
  );
}

const styles = StyleSheet.create({
  body: {
    gap: spacing.md,
  },
});
