import { RequireGlobalOperator, RequirePermissions } from "./auth/RequirePermissions";
import { AdminLayout, AppLayout } from "./layout/AppLayout";
import {
  AdminDashboardPage,
  AdminLeaguesPage,
  AdminUsersPage,
  AuctionPage,
  AuthRegisterPage,
  AuthPage,
  FormationPage,
  LeagueAdminPage,
  LeaguesPage,
  MarketPage,
  MatchdayPage,
  NotFoundPage,
  ProfilePage,
  RosterPage,
  StandingsPage,
} from "./pages/AppPages";
import { DevShowcasePage } from "./pages/DevShowcasePage";
import { WireframesHubPage } from "./pages/WireframesHubPage";
import { useLocation } from "./router/simpleRouter";

function AppSection({ children }: { children: React.ReactNode }) {
  return <AppLayout>{children}</AppLayout>;
}

function AdminSection({ children }: { children: React.ReactNode }) {
  return (
    <RequireGlobalOperator>
      <AdminLayout>{children}</AdminLayout>
    </RequireGlobalOperator>
  );
}

export function AppRoutes() {
  const { pathname } = useLocation();

  if (pathname === "/accedi") {
    return <AuthPage />;
  }

  if (pathname === "/accedi/registrati") {
    return <AuthRegisterPage />;
  }

  if (pathname === "/" || pathname === "/leghe") {
    return (
      <AppSection>
        <RequirePermissions required={["league:view"]}>
          <LeaguesPage />
        </RequirePermissions>
      </AppSection>
    );
  }

  if (pathname === "/turni") {
    return (
      <AppSection>
        <RequirePermissions required={["matchday:view"]}>
          <MatchdayPage />
        </RequirePermissions>
      </AppSection>
    );
  }

  if (pathname === "/classifica") {
    return (
      <AppSection>
        <RequirePermissions required={["matchday:view"]}>
          <StandingsPage />
        </RequirePermissions>
      </AppSection>
    );
  }

  if (pathname === "/rosa") {
    return (
      <AppSection>
        <RequirePermissions required={["roster:view"]}>
          <RosterPage />
        </RequirePermissions>
      </AppSection>
    );
  }

  if (pathname === "/formazione") {
    return (
      <AppSection>
        <RequirePermissions required={["roster:view"]}>
          <FormationPage />
        </RequirePermissions>
      </AppSection>
    );
  }

  if (pathname === "/asta") {
    return (
      <AppSection>
        <RequirePermissions required={["market:view"]}>
          <AuctionPage />
        </RequirePermissions>
      </AppSection>
    );
  }

  if (pathname === "/mercato") {
    return (
      <AppSection>
        <RequirePermissions required={["market:view"]}>
          <MarketPage />
        </RequirePermissions>
      </AppSection>
    );
  }

  if (pathname === "/lega/amministrazione") {
    return (
      <AppSection>
        <RequirePermissions required={["league:admin"]}>
          <LeagueAdminPage />
        </RequirePermissions>
      </AppSection>
    );
  }

  if (pathname === "/profilo") {
    return (
      <AppSection>
        <RequirePermissions required={["profile:view"]}>
          <ProfilePage />
        </RequirePermissions>
      </AppSection>
    );
  }

  if (pathname === "/dev/design-system") {
    return (
      <AppSection>
        <DevShowcasePage />
      </AppSection>
    );
  }

  if (pathname === "/dev/wireframes") {
    return (
      <AppSection>
        <WireframesHubPage />
      </AppSection>
    );
  }

  if (pathname === "/admin") {
    return (
      <AdminSection>
        <RequirePermissions required={["global:operate"]}>
          <AdminDashboardPage />
        </RequirePermissions>
      </AdminSection>
    );
  }

  if (pathname === "/admin/leghe") {
    return (
      <AdminSection>
        <RequirePermissions required={["global:operate"]}>
          <AdminLeaguesPage />
        </RequirePermissions>
      </AdminSection>
    );
  }

  if (pathname === "/admin/utenti") {
    return (
      <AdminSection>
        <RequirePermissions required={["global:operate"]}>
          <AdminUsersPage />
        </RequirePermissions>
      </AdminSection>
    );
  }

  return <NotFoundPage />;
}
