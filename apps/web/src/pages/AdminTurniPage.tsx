import type { AdminLeagueTurnStatus } from "@fantappero/contracts";
import {
  Badge,
  Breadcrumb,
  Button,
  Card,
  CardBody,
  CardHeader,
  Input,
  PageContainer,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  UiStatePanel,
} from "@fantappero/ui";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  calculateCurrentRoundsAllLeagues,
  fetchAdminLeagueTurnStatus,
  generateAllAiLineups,
  repairHistoricalRounds,
  syncAllLeagueTurns,
  syncCalendarForAllLeagues,
} from "../api/admin";
import {
  calculateCurrentRound,
  openFantasyTurn,
  recalculateFantasyTurnCutoff,
  runAiLineups,
} from "../api/leagues";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";

const COMMAND_LEGEND: { label: string; description: string }[] = [
  {
    label: "Sincronizza turni",
    description: "Apre i turni pronti e ricalcola i cutoff per tutte le leghe attive.",
  },
  {
    label: "Genera calendario",
    description:
      "Sincronizza partite, date e Turni Europei con il provider e riallinea il calendario della lega.",
  },
  {
    label: "Genera formazioni IA",
    description:
      "Genera automaticamente le formazioni esclusivamente per gli utenti/squadre gestiti dall'AI secondo le regole previste.",
  },
  {
    label: "Calcola giornata corrente",
    description:
      "Calcola punteggi, risultati e classifica della giornata corrente utilizzando le formazioni disponibili (con fallback per quelle mancanti).",
  },
  {
    label: "Ricalcola storico",
    description:
      "Riapre (se serve, motivo obbligatorio) e ricalcola i turni con formazioni mai risolte nello storico. Può correggere turni già omologati.",
  },
  {
    label: "Apri turno",
    description:
      "Apre manualmente un turno programmato, senza aspettare l'omologazione automatica del turno precedente.",
  },
  {
    label: "Ricalcola cutoff",
    description: "Ricalcola il cutoff del turno dagli orari reali delle partite aggiornati dal provider.",
  },
];

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
  const [query, setQuery] = useState("");

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

  const [calculatingRounds, setCalculatingRounds] = useState(false);
  const [calculateResult, setCalculateResult] = useState<string | null>(null);
  const [calculateError, setCalculateError] = useState<string | null>(null);

  const [repairReason, setRepairReason] = useState("");
  const [repairingHistory, setRepairingHistory] = useState(false);
  const [repairProgress, setRepairProgress] = useState<{
    percent: number;
    message: string;
  } | null>(null);
  const [repairResult, setRepairResult] = useState<string | null>(null);
  const [repairError, setRepairError] = useState<string | null>(null);

  const visibleLeagues = useMemo(() => {
    const trimmed = query.trim().toLowerCase();
    if (!trimmed) {
      return leagues;
    }
    return leagues.filter(
      (league) =>
        league.leagueName.toLowerCase().includes(trimmed) ||
        league.leagueId.toLowerCase().includes(trimmed),
    );
  }, [leagues, query]);

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

  async function onCalculateRounds() {
    const session = loadStoredSession();
    if (!session?.accessToken) {
      return;
    }
    setCalculatingRounds(true);
    setCalculateError(null);
    setCalculateResult(null);
    try {
      const result = await calculateCurrentRoundsAllLeagues(session.accessToken);
      setCalculateResult(
        `Turni considerati: ${result.roundsConsidered}, elaborati: ${result.roundsProcessed}, ` +
          `omologati: ${result.roundsFinalized}. Partite valutate: ${result.fixturesScored}.`,
      );
      await load();
    } catch (error) {
      setCalculateError(getApiErrorMessage(error, "Calcolo giornata corrente non riuscito."));
    } finally {
      setCalculatingRounds(false);
    }
  }

  async function onRepairHistory() {
    const session = loadStoredSession();
    if (!session?.accessToken || !repairReason.trim()) {
      return;
    }
    setRepairingHistory(true);
    setRepairError(null);
    setRepairResult(null);
    setRepairProgress({ percent: 0, message: "Avvio in corso…" });
    try {
      const result = await repairHistoricalRounds(session.accessToken, repairReason.trim(), {
        onProgress: (progress) =>
          setRepairProgress({ percent: progress.percent, message: progress.message }),
      });
      setRepairResult(
        `Leghe attive: ${result.leagues}, turni con un buco storico: ${result.roundsConsidered}, ` +
          `riparati: ${result.roundsRepaired}, falliti: ${result.roundsFailed}.`,
      );
      await load();
    } catch (error) {
      setRepairError(getApiErrorMessage(error, "Ricalcolo storico non riuscito."));
    } finally {
      setRepairingHistory(false);
      setRepairProgress(null);
    }
  }

  async function onCalculateRound(leagueId: string, roundId: string) {
    const session = loadStoredSession();
    if (!session?.accessToken) {
      return;
    }
    setRowBusy(`calculate-${roundId}`);
    setRowError(null);
    setRowMessage(null);
    try {
      const result = await calculateCurrentRound(session.accessToken, leagueId, roundId);
      setRowMessage(
        result.homologated
          ? `Turno ${result.roundNumber} calcolato e omologato.`
          : `Turno ${result.roundNumber} calcolato (dati non ancora definitivi).`,
      );
      await load();
    } catch (error) {
      setRowError(getApiErrorMessage(error, "Calcolo giornata non riuscito."));
    } finally {
      setRowBusy(null);
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
      <Card data-testid="admin-turni-legend">
        <CardHeader title="Cosa fanno questi comandi?" />
        <CardBody>
          <dl className="fa-ds-showcase__stack">
            {COMMAND_LEGEND.map((item) => (
              <div key={item.label}>
                <dt style={{ fontWeight: 600 }}>{item.label}</dt>
                <dd style={{ margin: 0 }}>{item.description}</dd>
              </div>
            ))}
          </dl>
        </CardBody>
      </Card>

      <Card data-testid="admin-turni-massive">
        <CardHeader title="Azioni massive — tutte le leghe attive" />
        <CardBody>
          <p>
            Apertura turno, ricalcolo cutoff, generazione calendario, formazioni IA e calcolo
            giornata sono automatici di default. Questi pulsanti forzano subito lo stesso ciclo
            che i cron eseguono periodicamente, per tutte le leghe attive insieme.
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
            <Button
              type="button"
              variant="secondary"
              loading={calculatingRounds}
              disabled={calculatingRounds}
              onClick={() => void onCalculateRounds()}
              data-testid="admin-turni-calculate-all"
            >
              Calcola giornata corrente
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

          {calculateResult ? (
            <UiStatePanel
              state="success"
              title="Giornata calcolata"
              message={calculateResult}
              testId="admin-turni-calculate-all-success"
            />
          ) : null}
          {calculateError ? (
            <UiStatePanel
              state="error"
              title="Calcolo non riuscito"
              message={calculateError}
              testId="admin-turni-calculate-all-error"
            />
          ) : null}
        </CardBody>
      </Card>

      <Card data-testid="admin-turni-repair">
        <CardHeader title="Ricalcola storico" />
        <CardBody>
          <p>
            Riapre (se serve) e ricalcola i turni con formazioni mai risolte nello storico —
            azione rara, distinta dal calcolo di routine: può correggere turni già omologati e
            invia notifiche di correzione agli utenti coinvolti. Richiede un motivo.
          </p>
          <Input
            label="Motivo della correzione"
            name="admin-turni-repair-reason"
            value={repairReason}
            onChange={(event) => setRepairReason(event.target.value)}
            placeholder="Es. recupero storico formazioni mancanti"
          />
          <Button
            type="button"
            variant="secondary"
            loading={repairingHistory}
            disabled={repairingHistory || !repairReason.trim()}
            onClick={() => void onRepairHistory()}
            data-testid="admin-turni-repair-all"
          >
            Ricalcola storico
          </Button>

          {repairingHistory ? (
            <UiStatePanel
              state="loading"
              title="Ricalcolo storico in corso"
              message={
                repairProgress
                  ? `${repairProgress.message} (${repairProgress.percent}%)`
                  : "Avvio in corso…"
              }
              testId="admin-turni-repair-all-progress"
            />
          ) : null}
          {!repairingHistory && repairResult ? (
            <UiStatePanel
              state="success"
              title="Storico ricalcolato"
              message={repairResult}
              testId="admin-turni-repair-all-success"
            />
          ) : null}
          {!repairingHistory && repairError ? (
            <UiStatePanel
              state="error"
              title="Ricalcolo non riuscito"
              message={repairError}
              testId="admin-turni-repair-all-error"
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
            <Input
              label="Cerca lega"
              name="admin-turni-query"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Nome o id della lega"
              data-testid="admin-turni-search"
            />
          ) : null}
          {!loading && !loadError && leagues.length > 0 && visibleLeagues.length === 0 ? (
            <UiStatePanel
              state="empty"
              title="Nessuna lega corrisponde"
              message="Nessuna lega attiva corrisponde alla ricerca."
              testId="admin-turni-search-empty"
            />
          ) : null}
          {!loading && !loadError && visibleLeagues.length > 0 ? (
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
                {visibleLeagues.map((league) => (
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
                          <Button
                            type="button"
                            variant="ghost"
                            disabled={rowBusy !== null}
                            loading={rowBusy === `calculate-${league.currentRoundId}`}
                            onClick={() =>
                              void onCalculateRound(league.leagueId, league.currentRoundId as string)
                            }
                            data-testid={`admin-turni-calculate-${league.leagueId}`}
                          >
                            Calcola giornata corrente
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
