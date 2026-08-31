import type { AdminLeagueTurnStatus } from "@fantappero/contracts";
import {
  Badge,
  Breadcrumb,
  Button,
  Card,
  CardBody,
  CardHeader,
  PageContainer,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  UiStatePanel,
} from "@fantappero/ui";
import { useCallback, useEffect, useState } from "react";
import {
  fetchAdminLeagueTurnStatus,
  generateAllAiLineups,
  syncAllLeagueTurns,
  syncCalendarForAllLeagues,
} from "../api/admin";
import {
  openFantasyTurn,
  recalculateFantasyTurnCutoff,
  runAiLineups,
} from "../api/leagues";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";

const ROUND_STATUS_LABEL: Record<string, string> = {
  scheduled: "Programmato",
  open: "Aperto",
  locked: "Chiuso",
  skipped: "Non disputato",
};

const HOMOLOGATION_LABEL: Record<string, string> = {
  provisional: "Provvisorio",
  homologated: "Omologato",
};

function formatDateTime(value: string | null): string {
  if (!value) {
    return "—";
  }
  try {
    return new Intl.DateTimeFormat("it-IT", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "Europe/Rome",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

/**
 * Pannello operatore — turni, calendario, formazioni IA (EP-turni-automazione).
 *
 * Apertura turno, ricalcolo cutoff, generazione calendario e formazioni IA
 * sono automatiche di default (cron periodici + apertura alla omologazione
 * del turno precedente). Questa pagina è l'override manuale dell'operatore
 * di piattaforma — l'admin di lega non ha più accesso a queste azioni:
 * sia massivo (tutte le leghe attive in un colpo) sia puntuale (una riga).
 */
export function AdminTurniPage() {
  const [leagues, setLeagues] = useState<AdminLeagueTurnStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [rowBusy, setRowBusy] = useState<string | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);
  const [rowMessage, setRowMessage] = useState<string | null>(null);

  const [syncingTurns, setSyncingTurns] = useState(false);
  const [turnsResult, setTurnsResult] = useState<string | null>(null);
  const [turnsError, setTurnsError] = useState<string | null>(null);

  const [generatingLineups, setGeneratingLineups] = useState(false);
  const [lineupsResult, setLineupsResult] = useState<string | null>(null);
  const [lineupsError, setLineupsError] = useState<string | null>(null);

  const [syncingCalendar, setSyncingCalendar] = useState(false);
  const [calendarProgress, setCalendarProgress] = useState<{
    percent: number;
    message: string;
  } | null>(null);
  const [calendarResult, setCalendarResult] = useState<string | null>(null);
  const [calendarError, setCalendarError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const session = loadStoredSession();
    if (!session?.accessToken) {
      setLoadError("Sessione non disponibile. Accedi di nuovo.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      setLeagues(await fetchAdminLeagueTurnStatus(session.accessToken));
    } catch (error) {
      setLoadError(getApiErrorMessage(error, "Impossibile caricare lo stato delle leghe."));
      setLeagues([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onSyncTurns() {
    const session = loadStoredSession();
    if (!session?.accessToken) {
      return;
    }
    setSyncingTurns(true);
    setTurnsError(null);
    setTurnsResult(null);
    try {
      const result = await syncAllLeagueTurns(session.accessToken);
      setTurnsResult(
        `Leghe: ${result.leagues}. Turni creati: ${result.created}, aperti: ${result.opened}, ` +
          `aggiornati: ${result.upgraded}, in attesa: ${result.waiting}.`,
      );
      await load();
    } catch (error) {
      setTurnsError(getApiErrorMessage(error, "Sincronizzazione turni non riuscita."));
    } finally {
      setSyncingTurns(false);
    }
  }

  async function onGenerateLineups() {
    const session = loadStoredSession();
    if (!session?.accessToken) {
      return;
    }
    setGeneratingLineups(true);
    setLineupsError(null);
    setLineupsResult(null);
    try {
      const result = await generateAllAiLineups(session.accessToken);
      setLineupsResult(
        `Turni processati: ${result.rounds}. Squadre aggiornate: ${result.teamsUpdated}, ` +
          `invariate: ${result.teamsSkipped}.`,
      );
    } catch (error) {
      setLineupsError(getApiErrorMessage(error, "Generazione formazioni IA non riuscita."));
    } finally {
      setGeneratingLineups(false);
    }
  }

  async function onSyncCalendar() {
    const session = loadStoredSession();
    if (!session?.accessToken) {
      return;
    }
    setSyncingCalendar(true);
    setCalendarError(null);
    setCalendarResult(null);
    setCalendarProgress({ percent: 0, message: "Avvio in corso…" });
    try {
      const result = await syncCalendarForAllLeagues(session.accessToken, {
        onProgress: (progress) =>
          setCalendarProgress({ percent: progress.percent, message: progress.message }),
      });
      setCalendarResult(
        `Leghe attive: ${result.leagues}, aggiornate: ${result.refreshed}, fallite: ${result.failed}. ` +
          `Fixture nuove: ${result.fixturesCreated}, aggiornate: ${result.fixturesUpdated}.`,
      );
      await load();
    } catch (error) {
      setCalendarError(getApiErrorMessage(error, "Aggiornamento calendario massivo non riuscito."));
    } finally {
      setSyncingCalendar(false);
      setCalendarProgress(null);
    }
  }

  async function onOpenRound(leagueId: string, roundId: string) {
    const session = loadStoredSession();
    if (!session?.accessToken) {
      return;
    }
    setRowBusy(`open-${roundId}`);
    setRowError(null);
    setRowMessage(null);
    try {
      const detail = await openFantasyTurn(session.accessToken, leagueId, roundId);
      setRowMessage(`Turno ${detail.number} aperto.`);
      await load();
    } catch (error) {
      setRowError(getApiErrorMessage(error, "Apertura turno non riuscita."));
    } finally {
      setRowBusy(null);
    }
  }

  async function onRecalculateCutoff(leagueId: string, roundId: string) {
    const session = loadStoredSession();
    if (!session?.accessToken) {
      return;
    }
    setRowBusy(`recalc-${roundId}`);
    setRowError(null);
    setRowMessage(null);
    try {
      await recalculateFantasyTurnCutoff(session.accessToken, leagueId, roundId);
      setRowMessage("Cutoff aggiornato dagli orari correnti.");
      await load();
    } catch (error) {
      setRowError(getApiErrorMessage(error, "Ricalcolo cutoff non riuscito."));
    } finally {
      setRowBusy(null);
    }
  }

  async function onGenerateRoundLineups(leagueId: string, roundId: string) {
    const session = loadStoredSession();
    if (!session?.accessToken) {
      return;
    }
    setRowBusy(`lineups-${roundId}`);
    setRowError(null);
    setRowMessage(null);
    try {
      const run = await runAiLineups(session.accessToken, leagueId, roundId, false);
      setRowMessage(run.summary);
    } catch (error) {
      setRowError(getApiErrorMessage(error, "Generazione formazioni IA non riuscita."));
    } finally {
      setRowBusy(null);
    }
  }

  return (
    <PageContainer
      title="Turni"
      header={<Breadcrumb items={[{ label: "Operazioni", href: "/admin" }, { label: "Turni" }]} />}
    >
      <Card data-testid="admin-turni-massive">
        <CardHeader title="Azioni massive — tutte le leghe attive" />
        <CardBody>
          <p>
            Apertura turno, ricalcolo cutoff, generazione calendario e formazioni IA sono
            automatiche di default. Questi pulsanti forzano subito lo stesso ciclo che i cron
            eseguono periodicamente, per tutte le leghe attive insieme.
          </p>
          <div className="fa-ds-showcase__row">
            <Button
              type="button"
              loading={syncingTurns}
              disabled={syncingTurns}
              onClick={() => void onSyncTurns()}
              data-testid="admin-turni-sync-all"
            >
              Sincronizza turni
            </Button>
            <Button
              type="button"
              variant="secondary"
              loading={syncingCalendar}
              disabled={syncingCalendar}
              onClick={() => void onSyncCalendar()}
              data-testid="admin-turni-calendar-sync-all"
            >
              Genera calendario
            </Button>
            <Button
              type="button"
              variant="secondary"
              loading={generatingLineups}
              disabled={generatingLineups}
              onClick={() => void onGenerateLineups()}
              data-testid="admin-turni-lineups-all"
            >
              Genera formazioni IA
            </Button>
          </div>

          {turnsResult ? (
            <UiStatePanel
              state="success"
              title="Turni sincronizzati"
              message={turnsResult}
              testId="admin-turni-sync-all-success"
            />
          ) : null}
          {turnsError ? (
            <UiStatePanel
              state="error"
              title="Sincronizzazione non riuscita"
              message={turnsError}
              testId="admin-turni-sync-all-error"
            />
          ) : null}

          {syncingCalendar ? (
            <UiStatePanel
              state="loading"
              title="Aggiornamento calendario in corso"
              message={
                calendarProgress
                  ? `${calendarProgress.message} (${calendarProgress.percent}%)`
                  : "Avvio in corso…"
              }
              testId="admin-turni-calendar-sync-all-progress"
            />
          ) : null}
          {!syncingCalendar && calendarResult ? (
            <UiStatePanel
              state="success"
              title="Calendario aggiornato"
              message={calendarResult}
              testId="admin-turni-calendar-sync-all-success"
            />
          ) : null}
          {!syncingCalendar && calendarError ? (
            <UiStatePanel
              state="error"
              title="Aggiornamento non riuscito"
              message={calendarError}
              testId="admin-turni-calendar-sync-all-error"
            />
          ) : null}

          {lineupsResult ? (
            <UiStatePanel
              state="success"
              title="Formazioni IA generate"
              message={lineupsResult}
              testId="admin-turni-lineups-all-success"
            />
          ) : null}
          {lineupsError ? (
            <UiStatePanel
              state="error"
              title="Generazione non riuscita"
              message={lineupsError}
              testId="admin-turni-lineups-all-error"
            />
          ) : null}
        </CardBody>
      </Card>

      <Card data-testid="admin-turni-leagues">
        <CardHeader title="Leghe attive" />
        <CardBody>
          {rowMessage ? (
            <UiStatePanel
              state="success"
              title="Azione completata"
              message={rowMessage}
              testId="admin-turni-row-success"
            />
          ) : null}
          {rowError ? (
            <UiStatePanel
              state="error"
              title="Azione non riuscita"
              message={rowError}
              testId="admin-turni-row-error"
            />
          ) : null}

          {loading ? (
            <UiStatePanel
              state="loading"
              title="Caricamento leghe"
              message="Recupero stato turni…"
              testId="admin-turni-loading"
            />
          ) : null}
          {!loading && loadError ? (
            <UiStatePanel
              state="error"
              title="Leghe non disponibili"
              message={loadError}
              testId="admin-turni-load-error"
            />
          ) : null}
          {!loading && !loadError && leagues.length === 0 ? (
            <UiStatePanel
              state="empty"
              title="Nessuna lega attiva"
              message="Non ci sono leghe in stato attivo al momento."
              testId="admin-turni-empty"
            />
          ) : null}
          {!loading && !loadError && leagues.length > 0 ? (
            <Table compact data-testid="admin-turni-table">
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Lega</TableHeaderCell>
                  <TableHeaderCell>Turno</TableHeaderCell>
                  <TableHeaderCell>Stato</TableHeaderCell>
                  <TableHeaderCell>Omologazione</TableHeaderCell>
                  <TableHeaderCell>Calendario aggiornato</TableHeaderCell>
                  <TableHeaderCell>Azioni</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {leagues.map((league) => (
                  <TableRow key={league.leagueId} data-testid={`admin-turni-row-${league.leagueId}`}>
                    <TableCell>{league.leagueName}</TableCell>
                    <TableCell>
                      {league.currentRoundNumber != null ? `Turno ${league.currentRoundNumber}` : "—"}
                    </TableCell>
                    <TableCell>
                      {league.currentRoundStatus ? (
                        <Badge variant="neutral">
                          {ROUND_STATUS_LABEL[league.currentRoundStatus] ?? league.currentRoundStatus}
                        </Badge>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                    <TableCell>
                      {league.homologationStatus ? (
                        <Badge
                          variant={league.homologationStatus === "homologated" ? "success" : "warning"}
                        >
                          {HOMOLOGATION_LABEL[league.homologationStatus] ?? league.homologationStatus}
                        </Badge>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                    <TableCell>{formatDateTime(league.calendarUpdatedAt)}</TableCell>
                    <TableCell>
                      {league.currentRoundId ? (
                        <div className="fa-ds-showcase__row">
                          <Button
                            type="button"
                            variant="ghost"
                            disabled={rowBusy !== null || league.currentRoundStatus !== "scheduled"}
                            loading={rowBusy === `open-${league.currentRoundId}`}
                            onClick={() =>
                              void onOpenRound(league.leagueId, league.currentRoundId as string)
                            }
                            data-testid={`admin-turni-open-${league.leagueId}`}
                          >
                            Apri turno
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            disabled={rowBusy !== null || league.currentRoundStatus === "skipped"}
                            loading={rowBusy === `recalc-${league.currentRoundId}`}
                            onClick={() =>
                              void onRecalculateCutoff(league.leagueId, league.currentRoundId as string)
                            }
                            data-testid={`admin-turni-recalc-${league.leagueId}`}
                          >
                            Ricalcola cutoff
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            disabled={rowBusy !== null}
                            loading={rowBusy === `lineups-${league.currentRoundId}`}
                            onClick={() =>
                              void onGenerateRoundLineups(
                                league.leagueId,
                                league.currentRoundId as string,
                              )
                            }
                            data-testid={`admin-turni-lineups-${league.leagueId}`}
                          >
                            Formazioni IA
                          </Button>
                        </div>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : null}
        </CardBody>
      </Card>
    </PageContainer>
  );
}
