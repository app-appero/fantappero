import type { AdminListoneEntry, FantasyRole } from "@fantappero/contracts";
import {
  Badge,
  Breadcrumb,
  Button,
  Card,
  CardBody,
  CardHeader,
  Input,
  PageContainer,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  TabList,
  TabPanel,
  Tabs,
  UiStatePanel,
} from "@fantappero/ui";
import { useCallback, useEffect, useState } from "react";
import { useListoneRefresh } from "../admin/ListoneRefreshContext";
import { fetchAdminListone } from "../api/admin";
import { ApiError } from "../api/client";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";

type RoleTab = "all" | FantasyRole;

const ROLE_TABS: Array<{ value: RoleTab; label: string }> = [
  { value: "all", label: "Tutti" },
  { value: "P", label: "Portieri" },
  { value: "D", label: "Difensori" },
  { value: "C", label: "Centrocampisti" },
  { value: "A", label: "Attaccanti" },
];

const ROLE_LABEL: Record<FantasyRole, string> = {
  P: "Portiere",
  D: "Difensore",
  C: "Centrocampista",
  A: "Attaccante",
};

const LISTONE_PAGE_SIZE = 20;

function roleBadgeVariant(role: FantasyRole): "success" | "warning" | "accent" | "danger" {
  if (role === "P") {
    return "success";
  }
  if (role === "D") {
    return "warning";
  }
  if (role === "C") {
    return "accent";
  }
  return "danger";
}

function filterEntries(
  entries: AdminListoneEntry[],
  tab: RoleTab,
  query: string,
): AdminListoneEntry[] {
  const normalized = query.trim().toLocaleLowerCase("it-IT");
  return entries.filter((entry) => {
    if (tab !== "all" && entry.officialRole !== tab) {
      return false;
    }
    if (!normalized) {
      return true;
    }
    const haystack = `${entry.canonicalName} ${entry.clubName ?? ""}`.toLocaleLowerCase("it-IT");
    return haystack.includes(normalized);
  });
}

function AdminListoneTable({ tabValue, rows }: { tabValue: RoleTab; rows: AdminListoneEntry[] }) {
  const [page, setPage] = useState(0);
  useEffect(() => {
    setPage(0);
  }, [rows]);
  const pageCount = Math.max(1, Math.ceil(rows.length / LISTONE_PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const pagedRows = rows.slice(
    safePage * LISTONE_PAGE_SIZE,
    safePage * LISTONE_PAGE_SIZE + LISTONE_PAGE_SIZE,
  );

  return (
    <>
      <Table compact data-testid={`admin-listone-table-${tabValue}`}>
        <TableHead>
          <TableRow>
            <TableHeaderCell>Calciatore</TableHeaderCell>
            <TableHeaderCell>Ruolo</TableHeaderCell>
            <TableHeaderCell>Club</TableHeaderCell>
            <TableHeaderCell>Posizione provider</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {pagedRows.map((entry) => (
            <TableRow key={entry.athleteId}>
              <TableCell>{entry.canonicalName}</TableCell>
              <TableCell>
                <Badge variant={roleBadgeVariant(entry.officialRole)}>
                  {entry.officialRole}
                </Badge>{" "}
                {ROLE_LABEL[entry.officialRole]}
              </TableCell>
              <TableCell>{entry.clubName ?? "—"}</TableCell>
              <TableCell>{entry.providerPositionRaw ?? "—"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {pageCount > 1 ? (
        <div
          className="fa-admin-listone__pagination"
          data-testid={`admin-listone-pagination-${tabValue}`}
        >
          <Button
            type="button"
            variant="ghost"
            disabled={safePage === 0}
            onClick={() => setPage((current) => Math.max(0, current - 1))}
          >
            Precedente
          </Button>
          <span>
            Pagina {safePage + 1} di {pageCount} · {rows.length} calciatori
          </span>
          <Button
            type="button"
            variant="ghost"
            disabled={safePage >= pageCount - 1}
            onClick={() => setPage((current) => Math.min(pageCount - 1, current + 1))}
          >
            Successiva
          </Button>
        </div>
      ) : null}
    </>
  );
}

const CURRENT_YEAR = new Date().getFullYear();

export function AdminListonePage() {
  const [seasonYear, setSeasonYear] = useState(String(CURRENT_YEAR));
  const [entries, setEntries] = useState<AdminListoneEntry[]>([]);
  const [activeTab, setActiveTab] = useState<RoleTab>("all");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { refreshing, progress: refreshProgress, startRefresh } = useListoneRefresh();
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [refreshSuccess, setRefreshSuccess] = useState<string | null>(null);

  const load = useCallback(async () => {
    const year = Number(seasonYear);
    if (!Number.isInteger(year) || year < 2000) {
      setError("Inserisci un anno stagione valido.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    const session = loadStoredSession();
    if (!session?.accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      setLoading(false);
      return;
    }
    try {
      setEntries(await fetchAdminListone(session.accessToken, year));
    } catch (loadError) {
      if (loadError instanceof ApiError && loadError.status === 403) {
        setError("Non hai i permessi per consultare il listone.");
      } else {
        setError(getApiErrorMessage(loadError, "Impossibile caricare il listone."));
      }
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, [seasonYear]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onRefresh() {
    const year = Number(seasonYear);
    if (!Number.isInteger(year) || year < 2000) {
      setRefreshError("Inserisci un anno stagione valido.");
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken) {
      setRefreshError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setRefreshError(null);
    setRefreshSuccess(null);
    try {
      const result = await startRefresh(session.accessToken, year);
      setRefreshSuccess(
        `${result.message} Creati: ${result.counters.listoneCreated}, aggiornati: ${result.counters.listoneUpdated}.`,
      );
      await load();
    } catch (refreshErr) {
      setRefreshError(getApiErrorMessage(refreshErr, "Aggiornamento listone non riuscito."));
    }
  }

  return (
    <PageContainer
      title="Listone ufficiale"
      header={
        <Breadcrumb items={[{ label: "Operazioni", href: "/admin" }, { label: "Listone" }]} />
      }
    >
      <Card data-testid="admin-listone-card">
        <CardHeader>
          <div className="fa-admin-listone__header">
            <Input
              label="Stagione"
              name="admin-listone-season-year"
              type="number"
              value={seasonYear}
              onChange={(event) => setSeasonYear(event.target.value)}
            />
            <Button
              type="button"
              variant="primary"
              loading={refreshing}
              onClick={() => void onRefresh()}
              data-testid="admin-listone-refresh"
            >
              Aggiorna listone dal provider
            </Button>
          </div>
        </CardHeader>
        <CardBody>
          {refreshing ? (
            <UiStatePanel
              state="loading"
              title="Aggiornamento in corso"
              message={
                refreshProgress
                  ? `${refreshProgress.message} (${refreshProgress.percent}%)`
                  : "Avvio in corso…"
              }
              testId="admin-listone-refresh-progress"
            />
          ) : null}
          {!refreshing && refreshError ? (
            <UiStatePanel
              state="error"
              title="Aggiornamento non riuscito"
              message={refreshError}
              testId="admin-listone-refresh-error"
            />
          ) : null}
          {!refreshing && refreshSuccess ? (
            <UiStatePanel
              state="success"
              title="Listone aggiornato"
              message={refreshSuccess}
              testId="admin-listone-refresh-success"
            />
          ) : null}

          {loading ? (
            <UiStatePanel
              state="loading"
              title="Caricamento listone"
              message="Recupero calciatori e ruoli…"
              testId="admin-listone-loading"
            />
          ) : null}
          {!loading && error ? (
            <UiStatePanel
              state={error.includes("permessi") ? "forbidden" : "error"}
              title="Listone non disponibile"
              message={error}
              testId="admin-listone-error"
            />
          ) : null}
          {!loading && !error && entries.length === 0 ? (
            <UiStatePanel
              state="empty"
              title="Nessun calciatore"
              message="Il listone è vuoto per questa stagione. Aggiornalo dal provider."
              testId="admin-listone-empty-all"
            />
          ) : null}
          {!loading && !error && entries.length > 0 ? (
            <>
              <div className="fa-admin-listone__search">
                <Input
                  label="Cerca calciatore"
                  name="admin-listone-query"
                  value={query}
                  placeholder="Nome o club…"
                  onChange={(event) => setQuery(event.target.value)}
                  data-testid="admin-listone-search"
                />
              </div>
              <Tabs
                value={activeTab}
                onValueChange={(value) => setActiveTab(value as RoleTab)}
                aria-label="Filtra listone per ruolo"
              >
                <TabList>
                  {ROLE_TABS.map((tab) => (
                    <Tab key={tab.value} value={tab.value}>
                      {tab.label}
                    </Tab>
                  ))}
                </TabList>
                {ROLE_TABS.map((tab) => {
                  const rows = filterEntries(entries, tab.value, query);
                  return (
                    <TabPanel key={tab.value} value={tab.value}>
                      {rows.length === 0 ? (
                        <UiStatePanel
                          state="empty"
                          title="Nessun calciatore"
                          message={
                            query.trim()
                              ? "Nessun risultato per la ricerca corrente."
                              : "Nessun calciatore in questo ruolo."
                          }
                          testId={`admin-listone-empty-${tab.value}`}
                        />
                      ) : (
                        <AdminListoneTable tabValue={tab.value} rows={rows} />
                      )}
                    </TabPanel>
                  );
                })}
              </Tabs>
            </>
          ) : null}
        </CardBody>
      </Card>
    </PageContainer>
  );
}
