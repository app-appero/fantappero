import {
  AppHeader,
  AppShell,
  BottomNav,
  BrandLogo,
  LeagueSelector,
  SidebarNav,
} from "@fantappero/ui";
import { type ReactNode } from "react";
import { Link, useLocation } from "../router/simpleRouter";
import { useAuth } from "../auth/AuthContext";
import { ADMIN_NAV_ITEMS, APP_NAV_ITEMS, filterNavItems } from "../navigation/navConfig";
import {
  IconCart,
  IconLayout,
  IconShield,
  IconTrophy,
  IconUser,
  IconUsers,
} from "../navigation/NavIcons";
import { RouterBottomNavLink, RouterNavLinkAdapter } from "../navigation/RouterNavLink";
import { SkipLink } from "./SkipLink";

const APP_ICONS: Record<string, ReactNode> = {
  leagues: <IconTrophy />,
  matchday: <IconLayout />,
  standings: <IconTrophy />,
  roster: <IconUsers />,
  formation: <IconLayout />,
  auction: <IconCart />,
  market: <IconCart />,
  "league-admin": <IconShield />,
  profile: <IconUser />,
};

function NavIcon({ id }: { id: string }) {
  return APP_ICONS[id] ?? null;
}

export function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, leagues, activeLeagueId, setActiveLeagueId, can } = useAuth();
  const location = useLocation();
  const navItems = filterNavItems(APP_NAV_ITEMS, can, location.pathname).map((item) => ({
    id: item.id,
    label: item.label,
    href: item.path,
    active: item.active,
    icon: <NavIcon id={item.id} />,
  }));

  const showLeagueSelector = leagues.length > 0 && location.pathname !== "/leghe";

  return (
    <AppShell
      surface="app"
      className="fa-surface-pitch fa-surface-pitch--subtle"
      skipLink={<SkipLink />}
      header={
        <AppHeader
          brand={
            <Link to="/leghe" aria-label="FantApperò, home">
              <BrandLogo variant="full" size="sm" />
            </Link>
          }
          contextSlot={
            showLeagueSelector ? (
              <LeagueSelector
                label="Lega attiva"
                leagues={leagues.map((league) => ({
                  value: league.id,
                  label: league.name,
                }))}
                value={activeLeagueId ?? leagues[0]?.id ?? ""}
                onChange={setActiveLeagueId}
                placeholder="Seleziona lega"
              />
            ) : null
          }
          actionsSlot={
            <>
              {can(["global:operate"]) ? (
                <Link to="/admin" className="fa-link-muted" data-testid="admin-panel-link">
                  Pannello globale
                </Link>
              ) : null}
              <span className="fa-user-chip" data-testid="user-display">
                {user.displayName}
              </span>
            </>
          }
        />
      }
      sidebar={
        <SidebarNav
          items={navItems}
          linkComponent={RouterNavLinkAdapter}
          ariaLabel="Navigazione lega"
        />
      }
      bottomNav={
        <BottomNav
          items={navItems}
          linkComponent={RouterBottomNavLink}
          ariaLabel="Navigazione mobile lega"
        />
      }
    >
      {children}
    </AppShell>
  );
}

export function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user, can } = useAuth();
  const location = useLocation();
  const navItems = filterNavItems(ADMIN_NAV_ITEMS, can, location.pathname).map((item) => ({
    id: item.id,
    label: item.label,
    href: item.path,
    active: item.active,
    icon: <IconShield />,
  }));

  return (
    <AppShell
      surface="admin"
      skipLink={<SkipLink />}
      header={
        <AppHeader
          variant="admin"
          brand={
            <Link to="/admin" className="fa-admin-brand">
              FantApperò — Operazioni
            </Link>
          }
          actionsSlot={
            <>
              <Link to="/leghe" className="fa-link-muted">
                Torna all&apos;app
              </Link>
              <span className="fa-user-chip fa-user-chip--admin" data-testid="admin-user-display">
                {user.displayName}
              </span>
            </>
          }
        />
      }
      sidebar={
        <SidebarNav
          items={navItems}
          linkComponent={RouterNavLinkAdapter}
          ariaLabel="Navigazione operatore globale"
        />
      }
      bottomNav={
        <BottomNav
          items={navItems}
          linkComponent={RouterBottomNavLink}
          ariaLabel="Navigazione mobile operatore"
        />
      }
    >
      {children}
    </AppShell>
  );
}
