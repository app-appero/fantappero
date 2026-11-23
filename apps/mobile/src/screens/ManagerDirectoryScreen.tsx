import { lazyStyles } from "../theme/lazyStyles";
import { theme } from "@fantappero/ui/theme";
import { useCallback, useEffect, useState } from "react";
import { StyleSheet, View } from "react-native";
import { fetchLeagueAdminPanel, fetchLeagueMembers } from "../api/leagues";
import { fetchMarketGate } from "../api/market";
import { CoachDirectoryPanel } from "../components/CoachDirectoryPanel";
import { UiStatePanel } from "../components/UiStatePanel";
import { PageContainer } from "../layout/PageContainer";
import { useAuthSession } from "../session/DemoSessionContext";
import { directoryCountsRequest } from "./managerDirectoryCounts";

const { spacing } = theme;

/** Directory fantallenatori dedicata — allineata a web /fantallenatori. */
export function ManagerDirectoryScreen() {
  const { can, activeLeagueId, accessToken } = useAuthSession();
  const [reloadToken, setReloadToken] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [memberCount, setMemberCount] = useState(0);
  const [capacity, setCapacity] = useState(0);
  // Inviti nominativi in attesa accanto ai posti (Rosario, 20/11), dallo stato del mercato.
  const [pendingInviteCount, setPendingInviteCount] = useState(0);
  const [invitesReload, setInvitesReload] = useState(0);
  // Il permesso si guarda prima di caricare: a un semplice partecipante non serve nulla.
  const isAdmin = can(["league:admin"]);

  useEffect(() => {
    const request = directoryCountsRequest({ isAdmin, accessToken, leagueId: activeLeagueId });
    if (!request) {
      return;
    }
    let cancelled = false;
    void Promise.all([
      fetchLeagueAdminPanel(request.accessToken, request.leagueId),
      fetchLeagueMembers(request.accessToken, request.leagueId),
    ])
      .then(([panel, members]) => {
        if (cancelled) {
          return;
        }
        setCapacity(panel.rules.participantCount);
        setMemberCount(members.length);
      })
      .catch(() => {
        if (!cancelled) {
          setCapacity(0);
          setMemberCount(0);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [isAdmin, accessToken, activeLeagueId, reloadToken]);

  useEffect(() => {
    const request = directoryCountsRequest({ isAdmin, accessToken, leagueId: activeLeagueId });
    if (!request) {
      return;
    }
    let cancelled = false;
    void fetchMarketGate(request.accessToken, request.leagueId)
      .then((gate) => {
        if (!cancelled) {
          setPendingInviteCount(gate.pendingInviteCount ?? 0);
        }
      })
      .catch(() => {
        // Senza lo stato del mercato i posti si mostrano senza gli inviti in attesa.
      });
    return () => {
      cancelled = true;
    };
  }, [isAdmin, accessToken, activeLeagueId, reloadToken, invitesReload]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    setReloadToken((current) => current + 1);
  }, []);

  const onReloadSettled = useCallback(() => {
    setRefreshing(false);
  }, []);

  if (!isAdmin) {
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
          memberCount={memberCount}
          capacity={capacity}
          pendingInviteCount={pendingInviteCount}
          onInvitesChanged={() => setInvitesReload((current) => current + 1)}
          testIDPrefix="manager-directory"
          reloadToken={reloadToken}
          onReloadSettled={onReloadSettled}
        />
      </View>
    </PageContainer>
  );
}

const styles = lazyStyles(() => StyleSheet.create({
  body: {
    gap: spacing.md,
  },
}));
