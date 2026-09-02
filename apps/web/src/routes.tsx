import { RequireAuth } from "./auth/RequireAuth";
import { RequireGlobalOperator, RequirePermissions } from "./auth/RequirePermissions";
import { AdminLayout, AppLayout } from "./layout/AppLayout";
import {
  AdminDashboardPage,
  AdminLeaguesPage,
  AdminListonePage,
  AdminTurniPage,
  AdminUsersPage,
  AuthForgotPasswordPage,
  AuthLoginPage,
  AuthRegisterPage,
  AuthResetPasswordPage,
  AuthVerifyEmailPage,
  CreateLeaguePage,
  FormationPage,
  LeagueHubPage,
  JoinLeaguePage,
  MarketHubPage,
  MatchdayPage,
  MatchupDetailPage,
  ManagerDirectoryPage,
  CoachProfilePage,
  NotFoundPage,
  ProfilePage,
  ReceivedInvitesPage,
  StandingsPage,
} from "./pages/AppPages";
import { DevShowcasePage } from "./pages/DevShowcasePage";
import { FixtureDetailPage } from "./pages/FixtureDetailPage";
import { WireframesHubPage } from "./pages/WireframesHubPage";
import { useLocation } from "./router/simpleRouter";

function AppSection({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <AppLayout>{children}</AppLayout>
    </RequireAuth>
  );
}

function AdminSection({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <RequireGlobalOperator>
        <AdminLayout>{children}</AdminLayout>
      </RequireGlobalOperator>
    </RequireAuth>
  );
}

export function AppRoutes() {
  const { pathname } = useLocation();

  if (pathname === "/accedi") {
    return <AuthLoginPage />;
  }

  if (pathname === "/accedi/registrati") {
    return <AuthRegisterPage />;
  }

  if (pathname === "/accedi/recupera") {
    return <AuthForgotPasswordPage />;
  }

  if (pathname === "/accedi/reimposta-password") {
    return <AuthResetPasswordPage />;
  }

  if (pathname === "/accedi/verifica") {
    return <AuthVerifyEmailPage />;
  }

  if (pathname === "/" || pathname === "/leghe" || pathname === "/lega/home" || pathname === "/lega/amministrazione") {
    return (
      <AppSection>
        <RequirePermissions required={["league:view"]}>
          <LeagueHubPage />
        </RequirePermissions>
      </AppSection>
    );
  }

  if (pathname === "/leghe/crea") {
    return (
      <AppSection>
        <RequirePermissions required={["league:view"]}>
          <CreateLeaguePage />
        </RequirePermissions>
      </AppSection>
    );
  }

  if (pathname === "/leghe/invito") {
    return (
      <AppSection>
        <RequirePermissions required={["league:view"]}>
          <JoinLeaguePage />
        </RequirePermissions>
      </AppSection>
    );
  }

  if (pathname === "/fantallenatori") {
    return (
      <AppSection>
        <RequirePermissions required={["league:admin"]}>
          <ManagerDirectoryPage />
        </RequirePermissions>
      </AppSection>
    );
  }

  if (pathname.startsWith("/fantallenatori/")) {
    const userId = pathname.slice("/fantallenatori/".length);
    return (
      <AppSection>
        <RequirePermissions required={["league:admin"]}>
          <CoachProfilePage userId={userId} />
        </RequirePermissions>
      </AppSection>
    );
  }

  if (pathname === "/inviti") {
    return (
      <AppSection>
        <RequirePermissions required={["league:view"]}>
          <ReceivedInvitesPage />
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

  if (pathname.startsWith("/turni/scontro/")) {
    return (
      <AppSection>
        <RequirePermissions required={["matchday:view"]}>
          <MatchupDetailPage />
        </RequirePermissions>
      </AppSection>
    );
  }

  if (pathname.startsWith("/turni/") && pathname.includes("/partite/")) {
    return (
      <AppSection>
        <RequirePermissions required={["matchday:view"]}>
          <FixtureDetailPage />
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

  if (
    pathname === "/rosa" ||
    pathname === "/asta" ||
    pathname === "/svincoli" ||
    pathname === "/mercato"
  ) {
    return (
      <AppSection>
        <RequirePermissions required={["roster:view"]}>
          <MarketHubPage />
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
    if (!import.meta.env.DEV) {
      return <NotFoundPage />;
    }
    return (
      <AppSection>
        <DevShowcasePage />
      </AppSection>
    );
  }

  if (pathname === "/dev/wireframes") {
    if (!import.meta.env.DEV) {
      return <NotFoundPage />;
    }
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

  if (pathname === "/admin/listone") {
    return (
      <AdminSection>
        <RequirePermissions required={["global:operate"]}>
          <AdminListonePage />
        </RequirePermissions>
      </AdminSection>
    );
  }

  if (pathname === "/admin/turni") {
    return (
      <AdminSection>
        <RequirePermissions required={["global:operate"]}>
          <AdminTurniPage />
        </RequirePermissions>
      </AdminSection>
    );
  }

  return <NotFoundPage />;
}
