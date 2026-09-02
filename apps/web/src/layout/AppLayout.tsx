import {
  AppHeader,
  AppShell,
  BottomNav,
  BrandLogo,
  LeagueSelector,
  LockCountdown,
  SidebarNav,
} from "@fantappero/ui";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link, useLocation } from "../router/simpleRouter";
import { useAuth } from "../auth/AuthContext";
import { LogoutButton } from "../auth/LogoutButton";
import { fetchPendingInviteCount } from "../api/managerInvites";
import { loadStoredSession } from "../auth/sessionStorage";
import { useLockCountdown } from "../matchday/useLockCountdown";
import {
  ADMIN_NAV_ITEMS,
  APP_NAV_ITEMS,
  NAV_SHORT_LABELS,
  filterNavItems,
  resolveNavGroups,
} from "../navigation/navConfig";
import {
  IconCart,
  IconLayout,
  IconShield,
  IconTrophy,
  IconUser,
  IconUsers,
} from "../navigation/NavIcons";
import { RouterBottomNavLink, RouterNavLinkAdapter } from "../navigation/RouterNavLink";
import { NotificationCenter } from "../notifications/NotificationCenter";
import { SkipLink } from "./SkipLink";

const APP_ICONS: Record<string, ReactNode> = {
  leagues: <IconTrophy />,
  "league-home": <IconLayout />,
  "manager-directory": <IconUsers />,
  "received-invites": <IconUsers />,
  matchday: <IconLayout />,
  standings: <IconTrophy />,
  roster: <IconUsers />,
  formation: <IconLayout />,
  auction: <IconCart />,
  waiver: <IconCart />,
  market: <IconCart />,
  "league-admin": <IconShield />,
  profile: <IconUser />,
};

function NavIcon({ id }: { id: string }) {
  return APP_ICONS[id] ?? null;
}

/** Gruppi chiusi manualmente: conservati per la sessione corrente (EP13-P01). */
const COLLAPSED_GROUPS_STORAGE_KEY = "fa.nav.groups.collapsed";

function readCollapsedGroups(): string[] {
  try {
    const raw = window.sessionStorage.getItem(COLLAPSED_GROUPS_STORAGE_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : null;
    return Array.isArray(parsed) ? parsed.filter((id): id is string => typeof id === "string") : [];
  } catch {
    return [];
  }
}

function useCollapsedNavGroups() {
  const [collapsed, setCollapsed] = useState<string[]>(readCollapsedGroups);

  const toggle = useCallback((groupId: string) => {
    setCollapsed((current) => {
      const next = current.includes(groupId)
        ? current.filter((id) => id !== groupId)
        : [...current, groupId];
      try {
        window.sessionStorage.setItem(COLLAPSED_GROUPS_STORAGE_KEY, JSON.stringify(next));
      } catch {
        // sessionStorage non disponibile: lo stato resta valido in memoria.
      }
      return next;
    });
  }, []);

  return { collapsed, toggle };
}

/**
 * Conteggio inviti pendenti per il badge (EP13-P07).
 *
 * Nessun polling: il dato cambia raramente e si aggiorna quando la finestra
 * torna in primo piano, coerentemente con la sospensione a schermata inattiva
 * introdotta in EP13-P04.
 */
function usePendingInviteCount(enabled: boolean): number {
  const [count, setCount] = useState(0);

  const refresh = useCallback(async () => {
    if (!enabled) {
      setCount(0);
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setCount(0);
      return;
    }
    try {
      const result = await fetchPendingInviteCount(stored.accessToken);
      setCount(result.pendingInviteCount);
    } catch {
      // Il badge è accessorio: un errore non deve rompere la navigazione.
      setCount(0);
    }
  }, [enabled]);

  useEffect(() => {
    void refresh();
    if (typeof window === "undefined") {
      return;
    }
    const onFocus = () => void refresh();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [refresh]);

  return count;
}

export function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, leagues, activeLeagueId, setActiveLeagueId, can } = useAuth();
  const location = useLocation();
  const { collapsed, toggle } = useCollapsedNavGroups();
  const pendingInvites = usePendingInviteCount(can(["league:view"]));
  const resolvedItems = filterNavItems(APP_NAV_ITEMS, can, location.pathname);
  const navItems = resolvedItems.map((item) => ({
    id: item.id,
    label: item.label,
    href: item.path,
    active: item.active,
    icon: <NavIcon id={item.id} />,
    badgeCount: item.id === "received-invites" ? pendingInvites : undefined,
    badgeLabel:
      item.id === "received-invites" && pendingInvites > 0
        ? `${pendingInvites} inviti in attesa di risposta`
        : undefined,
  }));
  // La bottom nav resta piatta: una barra non annida sottomenu.
  const bottomNavItems = navItems.map((item) => ({
    ...item,
    label: NAV_SHORT_LABELS[item.id] ?? item.label,
  }));
  const navGroups = resolveNavGroups();
  const expandedGroupIds = navGroups
    .filter((group) => !collapsed.includes(group.id))
    .map((group) => group.id);

  const showLeagueSelector =
    leagues.length > 0 && location.pathname !== "/leghe" && location.pathname !== "/leghe/crea";
  const { countdown, refetch: refetchCountdown } = useLockCountdown(
    showLeagueSelector ? activeLeagueId ?? leagues[0]?.id ?? null : null,
  );

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
                accessory={
                  countdown ? (
                    <LockCountdown
                      state={countdown.state}
                      nextLockAt={countdown.nextLockAt}
                      onExpire={refetchCountdown}
                    />
                  ) : undefined
                }
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
              <NotificationCenter />
              <span className="fa-user-chip" data-testid="user-display">
                {user?.displayName ?? "Utente"}
              </span>
              <LogoutButton />
            </>
          }
        />
      }
      sidebar={
        <SidebarNav
          items={navItems}
          groups={navGroups}
          expandedGroupIds={expandedGroupIds}
          onToggleGroup={toggle}
          linkComponent={RouterNavLinkAdapter}
          ariaLabel="Navigazione lega"
        />
      }
      bottomNav={
        <BottomNav
          items={bottomNavItems}
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
                {user?.displayName ?? "Operatore"}
              </span>
              <LogoutButton />
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
