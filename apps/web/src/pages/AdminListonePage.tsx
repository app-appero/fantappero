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
import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchAdminListone, refreshAdminListone } from "../api/admin";
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

function filterByTab(entries: AdminListoneEntry[], tab: RoleTab): AdminListoneEntry[] {
  if (tab === "all") {
    return entries;
  }
  return entries.filter((entry) => entry.officialRole === tab);
}

const CURRENT_YEAR = new Date().getFullYear();

export function AdminListonePage() {
  const [seasonYear, setSeasonYear] = useState(String(CURRENT_YEAR));
  const [entries, setEntries] = useState<AdminListoneEntry[]>([]);
  const [activeTab, setActiveTab] = useState<RoleTab>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshProgress, setRefreshProgress] = useState<{
    percent: number;
    stage: string;
    message: string;
  } | null>(null);
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
    setRefreshing(true);
    setRefreshError(null);
    setRefreshSuccess(null);
    setRefreshProgress({ percent: 0, stage: "queued", message: "Avvio in corso…" });
    try {
      const result = await refreshAdminListone(session.accessToken, year, {
        onProgress: (progress) =>
          setRefreshProgress({
            percent: progress.percent,
            stage: progress.stage,
            message: progress.message,
          }),
      });
      setRefreshSuccess(
        `${result.message} Creati: ${result.counters.listoneCreated}, aggiornati: ${result.counters.listoneUpdated}.`,
      );
      await load();
    } catch (refreshErr) {
      setRefreshError(getApiErrorMessage(refreshErr, "Aggiornamento listone non riuscito."));
    } finally {
      setRefreshing(false);
      setRefreshProgress(null);
    }
  }

  const visibleEntries = useMemo(() => filterByTab(entries, activeTab), [activeTab, entries]);

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
          {!loading && !error ? (
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
              {ROLE_TABS.map((tab) => (
                <TabPanel key={tab.value} value={tab.value}>
                  {visibleEntries.length === 0 ? (
                    <UiStatePanel
                      state="empty"
                      title="Nessun calciatore"
                      message="Il listone è vuoto per questa stagione. Aggiornalo dal provider."
                      testId={`admin-listone-empty-${tab.value}`}
                    />
                  ) : (
                    <Table compact data-testid={`admin-listone-table-${tab.value}`}>
                      <TableHead>
                        <TableRow>
                          <TableHeaderCell>Calciatore</TableHeaderCell>
                          <TableHeaderCell>Ruolo</TableHeaderCell>
                          <TableHeaderCell>Club</TableHeaderCell>
                          <TableHeaderCell>Posizione provider</TableHeaderCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {visibleEntries.map((entry) => (
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
                  )}
                </TabPanel>
              ))}
            </Tabs>
          ) : null}
        </CardBody>
      </Card>
    </PageContainer>
  );
}
