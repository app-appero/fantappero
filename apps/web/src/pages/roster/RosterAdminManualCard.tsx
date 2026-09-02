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
import {
  ROLE_LABEL,
  ROLE_TABS,
  filterListone,
  roleBadgeVariant,
  type AthleteOwnership,
  type RoleTab,
} from "./rosterHelpers";

export function RosterAdminManualCard({
  isAdmin,
  adminLoadError,
  leagueTeams,
  targetTeam,
  emptySlotsCount,
  purchaseCredits,
  onPurchaseCreditsChange,
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
  purchaseCredits: string;
  onPurchaseCreditsChange: (value: string) => void;
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
  onAssignAthlete: (athleteId: string) => void | Promise<void>;
}) {
  return (
    <Card style={{ marginTop: "1rem" }} data-testid="roster-admin-manual">
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

            <div style={{ marginBottom: "0.75rem" }}>
              <Input
                label="Crediti acquisto"
                name="roster-purchase-credits"
                type="number"
                min={1}
                value={purchaseCredits}
                onChange={(event) => onPurchaseCreditsChange(event.target.value)}
                data-testid="roster-purchase-credits"
              />
            </div>

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
                <div className="fa-roster-listone__search" style={{ marginBottom: "0.75rem" }}>
                  <Input
                    label="Cerca calciatore"
                    name="roster-listone-query"
                    value={listoneQuery}
                    placeholder="Nome o club…"
                    onChange={(event) => onListoneQueryChange(event.target.value)}
                    data-testid="roster-admin-listone-search"
                  />
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
                    const rows = filterListone(listone, tab.value, listoneQuery);
                    return (
                      <TabPanel key={tab.value} value={tab.value}>
                        {rows.length === 0 ? (
                          <UiStatePanel
                            state="empty"
                            title="Nessun calciatore"
                            message={
                              listoneQuery.trim()
                                ? "Nessun risultato per la ricerca corrente."
                                : tab.value === "all"
                                  ? "Il listone è vuoto."
                                  : `Nessun ${ROLE_LABEL[tab.value as FantasyRole].toLowerCase()} nel listone.`
                            }
                            testId={`roster-admin-listone-empty-${tab.value}`}
                          />
                        ) : (
                          <Table compact data-testid={`roster-admin-listone-table-${tab.value}`}>
                            <TableHead>
                              <TableRow>
                                <TableHeaderCell>Calciatore</TableHeaderCell>
                                <TableHeaderCell>Ruolo</TableHeaderCell>
                                <TableHeaderCell>Club</TableHeaderCell>
                                <TableHeaderCell>Stato</TableHeaderCell>
                                <TableHeaderCell>Azione</TableHeaderCell>
                              </TableRow>
                            </TableHead>
                            <TableBody>
                              {rows.map((entry) => {
                                const owner = ownership.get(entry.athleteId);
                                const canAssign = !owner && emptySlotsCount > 0;
                                const canRelease = owner ? canReleaseAthlete(owner.teamId) : false;
                                return (
                                  <TableRow key={entry.athleteId}>
                                    <TableCell>{entry.canonicalName}</TableCell>
                                    <TableCell>
                                      <Badge variant={roleBadgeVariant(entry.effectiveRole)}>
                                        {entry.effectiveRole}
                                      </Badge>{" "}
                                      {ROLE_LABEL[entry.effectiveRole]}
                                    </TableCell>
                                    <TableCell>{entry.clubName ?? "—"}</TableCell>
                                    <TableCell>
                                      {owner ? (
                                        <Badge variant="warning">In rosa: {owner.teamName}</Badge>
                                      ) : (
                                        <Badge variant="success">Libero</Badge>
                                      )}
                                    </TableCell>
                                    <TableCell>
                                      {owner && canRelease ? (
                                        <Button
                                          type="button"
                                          variant="secondary"
                                          disabled={adminBusy}
                                          data-testid={`roster-admin-release-${entry.athleteId}`}
                                          onClick={() => void onReleaseAthlete(entry.athleteId)}
                                        >
                                          Rimuovi
                                        </Button>
                                      ) : !owner ? (
                                        <Button
                                          type="button"
                                          variant="secondary"
                                          disabled={adminBusy || !canAssign}
                                          data-testid={`roster-admin-assign-${entry.athleteId}`}
                                          onClick={() => void onAssignAthlete(entry.athleteId)}
                                        >
                                          Assegna
                                        </Button>
                                      ) : null}
                                    </TableCell>
                                  </TableRow>
                                );
                              })}
                            </TableBody>
                          </Table>
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
