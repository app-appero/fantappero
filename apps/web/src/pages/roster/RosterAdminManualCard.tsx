import type {
  FantasyRole,
  FantasyTeam,
  FantasyTeamSummary,
  LeagueListoneEntry,
} from "@fantappero/contracts";
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  Input,
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
import { AthleteName } from "../../athletes/AthleteCard";
import { useEffect, useState } from "react";
import { RosterActionButton, RosterColLabel } from "./RosterActionButton";
import {
  LISTONE_PAGE_SIZE,
  ROLE_LABEL,
  ROLE_TABS,
  filterListone,
  roleBadgeVariant,
  type AthleteOwnership,
  type RoleTab,
} from "./rosterHelpers";

function ListoneAssignRow({
  entry,
  owner,
  canAssign,
  canRelease,
  adminBusy,
  onReleaseAthlete,
  onAssignAthlete,
}: {
  entry: LeagueListoneEntry;
  owner: AthleteOwnership | undefined;
  canAssign: boolean;
  canRelease: boolean;
  adminBusy: boolean;
  onReleaseAthlete: (athleteId: string) => void | Promise<void>;
  onAssignAthlete: (athleteId: string, purchaseCredits: number) => void | Promise<void>;
}) {
  const [draft, setDraft] = useState("1");
  const parsed = Number.parseInt(draft, 10);
  const isValid = Number.isFinite(parsed) && parsed >= 1;

  return (
    <TableRow>
      <TableCell className="fa-roster-col fa-roster-col--name">
        <AthleteName athleteId={entry.athleteId}>{entry.canonicalName}</AthleteName>
      </TableCell>
      <TableCell className="fa-roster-col fa-roster-col--role">
        <Badge variant={roleBadgeVariant(entry.effectiveRole)}>{entry.effectiveRole}</Badge>
        <span className="fa-roster-role-label"> {ROLE_LABEL[entry.effectiveRole]}</span>
      </TableCell>
      <TableCell className="fa-roster-col fa-roster-col--club">{entry.clubName ?? "—"}</TableCell>
      <TableCell className="fa-roster-col fa-roster-col--status">
        {owner ? (
          <Badge variant="warning">
            <RosterColLabel full={`In rosa: ${owner.teamName}`} short={owner.teamName} />
          </Badge>
        ) : (
          <Badge variant="success">Libero</Badge>
        )}
      </TableCell>
      <TableCell className="fa-roster-col fa-roster-col--price">
        {!owner ? (
          <Input
            className="fa-roster-price-input"
            type="number"
            min={1}
            aria-label={`Prezzo acquisto ${entry.canonicalName}`}
            value={draft}
            disabled={adminBusy || !canAssign}
            onChange={(event) => setDraft(event.target.value)}
            data-testid={`roster-admin-listone-price-${entry.athleteId}`}
          />
        ) : (
          "—"
        )}
      </TableCell>
      <TableCell className="fa-roster-col fa-roster-col--action">
        {owner && canRelease ? (
          <RosterActionButton
            action="release"
            disabled={adminBusy}
            testId={`roster-admin-release-${entry.athleteId}`}
            label={`Rimuovi ${entry.canonicalName}`}
            onClick={() => void onReleaseAthlete(entry.athleteId)}
          />
        ) : !owner ? (
          <RosterActionButton
            action="assign"
            disabled={adminBusy || !canAssign || !isValid}
            testId={`roster-admin-assign-${entry.athleteId}`}
            label={`Assegna ${entry.canonicalName}`}
            onClick={() => void onAssignAthlete(entry.athleteId, parsed)}
          />
        ) : null}
      </TableCell>
    </TableRow>
  );
}

function ListoneTable({
  tabValue,
  rows,
  ownership,
  canReleaseAthlete,
  emptySlotsCount,
  adminBusy,
  listoneQuery,
  onlyFree,
  onReleaseAthlete,
  onAssignAthlete,
}: {
  tabValue: RoleTab;
  rows: LeagueListoneEntry[];
  ownership: Map<string, AthleteOwnership>;
  canReleaseAthlete: (ownerTeamId: string) => boolean;
  emptySlotsCount: number;
  adminBusy: boolean;
  listoneQuery: string;
  onlyFree: boolean;
  onReleaseAthlete: (athleteId: string) => void | Promise<void>;
  onAssignAthlete: (athleteId: string, purchaseCredits: number) => void | Promise<void>;
}) {
  const [page, setPage] = useState(0);
  const availabilityKey = listoneQuery.trim() ? "search" : onlyFree ? "free" : "all";
  useEffect(() => {
    setPage(0);
  }, [listoneQuery, tabValue, availabilityKey]);
  const pageCount = Math.max(1, Math.ceil(rows.length / LISTONE_PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const pagedRows = rows.slice(
    safePage * LISTONE_PAGE_SIZE,
    safePage * LISTONE_PAGE_SIZE + LISTONE_PAGE_SIZE,
  );

  return (
    <>
      <Table compact className="fa-roster-table fa-roster-table--listone" data-testid={`roster-admin-listone-table-${tabValue}`}>
        <TableHead>
          <TableRow>
            <TableHeaderCell className="fa-roster-col fa-roster-col--name">
              <RosterColLabel full="Calciatore" short="Nome" />
            </TableHeaderCell>
            <TableHeaderCell className="fa-roster-col fa-roster-col--role">
              <RosterColLabel full="Ruolo" short="" />
            </TableHeaderCell>
            <TableHeaderCell className="fa-roster-col fa-roster-col--club">Club</TableHeaderCell>
            <TableHeaderCell className="fa-roster-col fa-roster-col--status">Stato</TableHeaderCell>
            <TableHeaderCell className="fa-roster-col fa-roster-col--price">
              <RosterColLabel full="Prezzo acquisto" short="Cr" />
            </TableHeaderCell>
            <TableHeaderCell className="fa-roster-col fa-roster-col--action">
              <RosterColLabel full="Azione" short="" />
            </TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {pagedRows.map((entry) => {
            const owner = ownership.get(entry.athleteId);
            const canAssign = !owner && emptySlotsCount > 0;
            const canRelease = owner ? canReleaseAthlete(owner.teamId) : false;
            return (
              <ListoneAssignRow
                key={entry.athleteId}
                entry={entry}
                owner={owner}
                canAssign={canAssign}
                canRelease={canRelease}
                adminBusy={adminBusy}
                onReleaseAthlete={onReleaseAthlete}
                onAssignAthlete={onAssignAthlete}
              />
            );
          })}
        </TableBody>
      </Table>
      {pageCount > 1 ? (
        <div
          className="fa-roster-role-section__pagination"
          data-testid={`roster-admin-listone-pagination-${tabValue}`}
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

export function RosterAdminManualCard({
  isAdmin,
  adminLoadError,
  leagueTeams,
  targetTeam,
  emptySlotsCount,
  adminMessage,
  adminError,
  listone,
  listoneQuery,
  onListoneQueryChange,
  roleTab,
  onRoleTabChange,
  ownership,
  canReleaseAthlete,
  adminBusy,
  onReleaseAthlete,
  onAssignAthlete,
}: {
  isAdmin: boolean;
  adminLoadError: string | null;
  leagueTeams: FantasyTeamSummary[];
  targetTeam: FantasyTeam | null;
  emptySlotsCount: number;
  adminMessage: string | null;
  adminError: string | null;
  listone: LeagueListoneEntry[];
  listoneQuery: string;
  onListoneQueryChange: (value: string) => void;
  roleTab: RoleTab;
  onRoleTabChange: (value: RoleTab) => void;
  ownership: Map<string, AthleteOwnership>;
  canReleaseAthlete: (ownerTeamId: string) => boolean;
  adminBusy: boolean;
  onReleaseAthlete: (athleteId: string) => void | Promise<void>;
  onAssignAthlete: (athleteId: string, purchaseCredits: number) => void | Promise<void>;
}) {
  const [onlyFree, setOnlyFree] = useState(false);
  const ownedAthleteIds = new Set(ownership.keys());
  return (
    <Card data-testid="roster-admin-manual">
      <CardHeader>
        <div className="fa-auction-listone__header">
          <div>
            <h2 className="fa-auction-listone__title">Inserimento manuale rose</h2>
            <p className="fa-auction-listone__subtitle">
              {isAdmin
                ? "Assegna o rimuovi calciatori dal listone sulla squadra target selezionata sopra."
                : "Assegna o rimuovi calciatori dal listone sulla tua rosa."}
            </p>
          </div>
        </div>
      </CardHeader>
      <CardBody>
        {adminLoadError ? (
          <UiStatePanel
            state="error"
            title="Caricamento non riuscito"
            message={adminLoadError}
            testId="roster-admin-manual-error"
          />
        ) : null}

        {isAdmin && leagueTeams.length === 0 ? (
          <UiStatePanel
            state="empty"
            title="Nessuna squadra"
            message="Assicura prima le squadre dei partecipanti."
            testId="roster-admin-manual-empty"
          />
        ) : !isAdmin && !targetTeam ? (
          <UiStatePanel
            state="empty"
            title="Nessuna squadra"
            message="La tua rosa non è ancora disponibile."
            testId="roster-admin-manual-empty"
          />
        ) : (
          <>
            {targetTeam ? (
              <p data-testid="roster-admin-team-summary">
                {targetTeam.name}: {targetTeam.filledSlots}/{targetTeam.rosterSize} slot ·{" "}
                {emptySlotsCount} liberi
              </p>
            ) : null}

            {adminMessage ? (
              <UiStatePanel
                state="success"
                title="Operazione riuscita"
                message={adminMessage}
                testId="roster-admin-ok"
              />
            ) : null}
            {adminError ? (
              <UiStatePanel
                state="error"
                title="Operazione non riuscita"
                message={adminError}
                testId="roster-admin-assign-error"
              />
            ) : null}

            {listone.length === 0 ? (
              <UiStatePanel
                state="empty"
                title="Listone vuoto"
                message="Il listone ufficiale non è ancora disponibile. Verrà popolato dagli operatori della piattaforma."
                testId="roster-admin-listone-empty"
              />
            ) : (
              <>
                <div className="fa-roster-listone__search">
                  <Input
                    label="Cerca calciatore"
                    name="roster-listone-query"
                    value={listoneQuery}
                    placeholder="Nome o club…"
                    onChange={(event) => onListoneQueryChange(event.target.value)}
                    data-testid="roster-admin-listone-search"
                  />
                  <label className="fa-roster-listone__free">
                    <input
                      type="checkbox"
                      checked={onlyFree}
                      onChange={(event) => setOnlyFree(event.target.checked)}
                      data-testid="roster-listone-only-free"
                    />
                    Solo disponibili
                  </label>
                </div>
                <Tabs
                  value={roleTab}
                  onValueChange={(value) => onRoleTabChange(value as RoleTab)}
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
                    const rows = filterListone(
                      listone,
                      tab.value,
                      listoneQuery,
                      onlyFree,
                      ownedAthleteIds,
                    );
                    return (
                      <TabPanel key={tab.value} value={tab.value}>
                        {rows.length === 0 ? (
                          <UiStatePanel
                            state="empty"
                            title="Nessun calciatore"
                            message={
                              listoneQuery.trim()
                                ? "Nessun risultato per la ricerca corrente."
                                : onlyFree
                                  ? "Nessun calciatore libero."
                                  : tab.value === "all"
                                    ? "Il listone è vuoto."
                                    : `Nessun ${ROLE_LABEL[tab.value as FantasyRole].toLowerCase()} nel listone.`
                            }
                            testId={`roster-admin-listone-empty-${tab.value}`}
                          />
                        ) : (
                          <ListoneTable
                            tabValue={tab.value}
                            rows={rows}
                            ownership={ownership}
                            canReleaseAthlete={canReleaseAthlete}
                            emptySlotsCount={emptySlotsCount}
                            adminBusy={adminBusy}
                            listoneQuery={listoneQuery}
                            onlyFree={onlyFree}
                            onReleaseAthlete={onReleaseAthlete}
                            onAssignAthlete={onAssignAthlete}
                          />
                        )}
                      </TabPanel>
                    );
                  })}
                </Tabs>
              </>
            )}
          </>
        )}
      </CardBody>
    </Card>
  );
}
