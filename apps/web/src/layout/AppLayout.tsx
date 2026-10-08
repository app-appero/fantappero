import {
  AppHeader,
  AppShell,
  Badge,
  BrandLogo,
  LeagueSelector,
  LockCountdown,
  NavDrawer,
  SidebarNav,
  type NavLinkAnchorProps,
} from "@fantappero/ui";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useLocation } from "../router/simpleRouter";
import { useAuth } from "../auth/AuthContext";
import { LogoutButton } from "../auth/LogoutButton";
import { leagueStateLabel } from "../leagues/leagueLabels";
import { useLockCountdown } from "../matchday/useLockCountdown";
import { usePendingInviteCount } from "./usePendingInviteCount";
import {
  ADMIN_NAV_ITEMS,
  APP_NAV_ITEMS,
  filterNavItems,
  resolveNavGroups,
} from "../navigation/navConfig";
import {
  IconCart,
  IconLayout,
  IconMenu,
  IconShield,
  IconTrophy,
  IconUser,
  IconUsers,
} from "../navigation/NavIcons";
import { RouterNavLinkAdapter } from "../navigation/RouterNavLink";
import { NotificationCenter } from "../notifications/NotificationCenter";
import { ImpersonationBanner } from "../auth/ImpersonationBanner";
import { SkipLink } from "./SkipLink";

const APP_ICONS: Record<string, ReactNode> = {
  "league-hub": <IconTrophy />,
  "manager-directory": <IconUsers />,
  "received-invites": <IconUsers />,
  matchday: <IconLayout />,
  standings: <IconTrophy />,
  "market-hub": <IconCart />,
  formation: <IconLayout />,
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
    return Array.isArray(parsed)
      ? parsed.filter((id): id is string => typeof id === "string")
      : [];
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
        window.sessionStorage.setItem(
          COLLAPSED_GROUPS_STORAGE_KEY,
          JSON.stringify(next),
        );
      } catch {
        // sessionStorage non disponibile: lo stato resta valido in memoria.
      }
      return next;
    });
  }, []);

  return { collapsed, toggle };
}

function useMobileNavDrawer() {
  const [open, setOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") {
      return;
    }
    const mq = window.matchMedia("(min-width: 768px)");
    const onChange = () => {
      if (mq.matches) {
        setOpen(false);
      }
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const close = useCallback(() => setOpen(false), []);
  const openDrawer = useCallback(() => setOpen(true), []);

  return { open, close, openDrawer };
}

function MenuButton({ open, onOpen }: { open: boolean; onOpen: () => void }) {
  return (
    <button
      type="button"
      className="fa-app-header__menu-button"
      aria-label="Apri menu"
      aria-expanded={open}
      aria-controls="nav-drawer-panel"
      data-testid="app-menu-button"
      onClick={onOpen}
    >
      <IconMenu />
    </button>
  );
}

/** Su schermi stretti il + apre crea/unisciti; i link restano nel DOM anche da chiuso. */
function HeaderLeagueActions() {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const { pathname } = useLocation();

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div className="fa-app-header__league-actions" ref={rootRef}>
      <button
        type="button"
        className="fa-app-header__add-league"
        aria-label="Crea o unisciti a una lega"
        aria-expanded={open}
        aria-controls="header-league-menu"
        data-testid="header-add-league"
        onClick={() => setOpen((value) => !value)}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </button>
      <div
        id="header-league-menu"
        className={
          open
            ? "fa-app-header__league-menu is-open"
            : "fa-app-header__league-menu"
        }
        data-testid="header-league-menu"
      >
        <Link
          to="/leghe/crea"
          className="fa-app-header__league-action"
          data-testid="header-create-league-link"
          onClick={() => setOpen(false)}
        >
          Crea lega
        </Link>
        <span className="fa-app-header__league-action-sep" aria-hidden="true">
          o
        </span>
        <Link
          to="/leghe/invito"
          className="fa-app-header__league-action"
          data-testid="header-join-league-link"
          onClick={() => setOpen(false)}
        >
          Unisciti con codice
        </Link>
      </div>
    </div>
  );
}

function DrawerNavLink({
  onNavigate,
  ...props
}: NavLinkAnchorProps & { onNavigate: () => void }) {
  return (
    <RouterNavLinkAdapter
      {...props}
      onClick={(event) => {
        props.onClick?.(event);
        onNavigate();
      }}
    />
  );
}

export function AppLayout({ children }: { children: React.ReactNode }) {
  const {
    user,
    leagues,
    leaguesError,
    refreshLeagues,
    activeLeagueId,
    setActiveLeagueId,
    can,
    isImpersonating,
  } = useAuth();
  const location = useLocation();
  const {
    open: drawerOpen,
    close: closeDrawer,
    openDrawer,
  } = useMobileNavDrawer();
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
  const navGroups = resolveNavGroups();
  const expandedGroupIds = navGroups
    .filter((group) => !collapsed.includes(group.id))
    .map((group) => group.id);
  const renderDrawerLink = useCallback(
    (props: NavLinkAnchorProps) => (
      <DrawerNavLink {...props} onNavigate={closeDrawer} />
    ),
    [closeDrawer],
  );

  const canSeeLeagueContext = can(["league:view"]);
  const activeLeagueSummary = leagues.find(
    (league) => league.id === (activeLeagueId ?? leagues[0]?.id),
  );
  const { countdown, refetch: refetchCountdown } = useLockCountdown(
    canSeeLeagueContext && leagues.length > 0
      ? (activeLeagueId ?? leagues[0]?.id ?? null)
      : null,
  );

  return (
    <>
      {isImpersonating ? <ImpersonationBanner /> : null}
      <AppShell
        surface="app"
        className="fa-surface-pitch fa-surface-pitch--subtle"
        skipLink={<SkipLink />}
        header={
          <AppHeader
            menuSlot={<MenuButton open={drawerOpen} onOpen={openDrawer} />}
            brand={
              <Link to="/leghe" aria-label="FantApperò, home">
                <BrandLogo variant="full" size="sm" />
              </Link>
            }
            contextSlot={
              canSeeLeagueContext ? (
                <div className="fa-app-header__league-context">
                  {leagues.length > 0 ? (
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
                        <>
                          {activeLeagueSummary ? (
                            <Badge
                              variant="neutral"
                              data-testid="active-league-status"
                            >
                              {leagueStateLabel(activeLeagueSummary.state)}
                            </Badge>
                          ) : null}
                          {countdown ? (
                            <LockCountdown
                              state={countdown.state}
                              nextLockAt={countdown.nextLockAt}
                              onExpire={refetchCountdown}
                            />
                          ) : null}
                        </>
                      }
                    />
                  ) : null}
                  <HeaderLeagueActions />
                  {leaguesError ? (
                    <p
                      className="fa-field__error"
                      role="alert"
                      data-testid="leagues-load-error"
                    >
                      {leaguesError}{" "}
                      <button
                        type="button"
                        className="fa-app-header__league-action"
                        onClick={() => void refreshLeagues()}
                      >
                        Riprova
                      </button>
                    </p>
                  ) : null}
                </div>
              ) : null
            }
            actionsSlot={
              <>
                {can(["global:operate"]) ? (
                  <Link
                    to="/admin"
                    className="fa-link-muted fa-app-header__desktop-only"
                    data-testid="admin-panel-link"
                  >
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
        overlay={
          <NavDrawer
            open={drawerOpen}
            onClose={closeDrawer}
            brand={
              <Link
                to="/leghe"
                aria-label="FantApperò, home"
                onClick={closeDrawer}
              >
                <BrandLogo variant="full" size="sm" />
              </Link>
            }
            userDisplayName={user?.displayName ?? "Utente"}
            footer={
              <div
                className="fa-nav-drawer__logout"
                data-testid="nav-drawer-logout"
              >
                <LogoutButton />
              </div>
            }
          >
            <SidebarNav
              items={navItems}
              groups={navGroups}
              expandedGroupIds={expandedGroupIds}
              onToggleGroup={toggle}
              linkComponent={renderDrawerLink}
              ariaLabel="Navigazione lega"
            />
            {can(["global:operate"]) ? (
              <Link
                to="/admin"
                className="fa-sidebar-nav__link fa-nav-drawer__extra"
                data-testid="admin-panel-link-drawer"
                onClick={closeDrawer}
              >
                Pannello globale
              </Link>
            ) : null}
          </NavDrawer>
        }
      >
        {children}
      </AppShell>
    </>
  );
}

export function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user, can } = useAuth();
  const location = useLocation();
  const {
    open: drawerOpen,
    close: closeDrawer,
    openDrawer,
  } = useMobileNavDrawer();
  const navItems = filterNavItems(ADMIN_NAV_ITEMS, can, location.pathname).map(
    (item) => ({
      id: item.id,
      label: item.label,
      href: item.path,
      active: item.active,
      icon: <IconShield />,
    }),
  );
  const renderDrawerLink = useCallback(
    (props: NavLinkAnchorProps) => (
      <DrawerNavLink {...props} onNavigate={closeDrawer} />
    ),
    [closeDrawer],
  );

  return (
    <AppShell
      surface="admin"
      skipLink={<SkipLink />}
      header={
        <AppHeader
          variant="admin"
          menuSlot={<MenuButton open={drawerOpen} onOpen={openDrawer} />}
          brand={
            <Link to="/admin" className="fa-admin-brand">
              FantApperò — Operazioni
            </Link>
          }
          actionsSlot={
            <>
              <Link
                to="/leghe"
                className="fa-link-muted fa-app-header__desktop-only"
              >
                Torna all&apos;app
              </Link>
              <span
                className="fa-user-chip fa-user-chip--admin"
                data-testid="admin-user-display"
              >
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
      overlay={
        <NavDrawer
          open={drawerOpen}
          onClose={closeDrawer}
          brand={
            <Link to="/admin" className="fa-admin-brand" onClick={closeDrawer}>
              FantApperò — Operazioni
            </Link>
          }
          userDisplayName={user?.displayName ?? "Operatore"}
          footer={
            <div
              className="fa-nav-drawer__logout"
              data-testid="nav-drawer-logout"
            >
              <LogoutButton />
            </div>
          }
        >
          <SidebarNav
            items={navItems}
            linkComponent={renderDrawerLink}
            ariaLabel="Navigazione operatore globale"
          />
          <Link
            to="/leghe"
            className="fa-sidebar-nav__link fa-nav-drawer__extra"
            onClick={closeDrawer}
          >
            Torna all&apos;app
          </Link>
        </NavDrawer>
      }
    >
      {children}
    </AppShell>
  );
}
