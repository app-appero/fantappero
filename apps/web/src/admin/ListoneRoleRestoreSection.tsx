import type { AdminListoneRoleRestoreResult, FantasyRole } from "@fantappero/contracts";
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  Input,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  UiStatePanel,
} from "@fantappero/ui";
import { useState } from "react";
import { restoreAdminListoneRoles } from "../api/admin";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";

/** L'ora prima dell'aggiornamento del 21/11 su pilota (ora di Roma). */
export const DEFAULT_RESTORE_BEFORE = "2026-11-21T12:00";

const ROME = "Europe/Rome";

function romeOffsetMs(utcMs: number): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: ROME,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).formatToParts(new Date(utcMs));
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    Number(parts.find((item) => item.type === type)?.value ?? "0");
  const wall = Date.UTC(
    part("year"),
    part("month") - 1,
    part("day"),
    part("hour"),
    part("minute"),
    part("second"),
  );
  return wall - utcMs;
}

/** "2026-11-21T12:00" (ora di Roma, qualunque sia il fuso del browser) → ISO in UTC. */
export function romeLocalToIso(value: string): string | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(value.trim());
  if (!match) {
    return null;
  }
  const [year, month, day, hour, minute] = match.slice(1, 6).map(Number) as [
    number,
    number,
    number,
    number,
    number,
  ];
  const wall = Date.UTC(year, month - 1, day, hour, minute);
  let utc = wall - romeOffsetMs(wall);
  utc = wall - romeOffsetMs(utc);
  return new Date(utc).toISOString();
}

function formatRome(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(value.trim());
  if (!match) {
    return value;
  }
  const [, year, month, day, hour, minute] = match;
  return `${day}/${month}/${year} alle ${hour}:${minute}`;
}

function RoleBadge({ role }: { role: FantasyRole | null }) {
  if (role === null) {
    return <span>non ricostruibile</span>;
  }
  return <Badge variant="accent">{role}</Badge>;
}

type Props = {
  seasonYear: number | null;
  /** Dopo un ripristino riuscito (per ricaricare il listone). */
  onRestored?: () => void;
};

export function ListoneRoleRestoreSection({ seasonYear, onRestored }: Props) {
  const [before, setBefore] = useState(DEFAULT_RESTORE_BEFORE);
  const [preview, setPreview] = useState<AdminListoneRoleRestoreResult | null>(null);
  const [busy, setBusy] = useState<"preview" | "apply" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [done, setDone] = useState<AdminListoneRoleRestoreResult | null>(null);

  async function call(dryRun: boolean) {
    const iso = romeLocalToIso(before);
    if (seasonYear === null || iso === null) {
      setError("Scegli una stagione e una data e ora valide.");
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setBusy(dryRun ? "preview" : "apply");
    setError(null);
    try {
      const athleteIds =
        !dryRun && preview
          ? preview.entries.filter((entry) => entry.reconstructible).map((entry) => entry.athleteId)
          : undefined;
      const result = await restoreAdminListoneRoles(session.accessToken, {
        seasonYear,
        before: iso,
        dryRun,
        athleteIds,
      });
      if (dryRun) {
        setPreview(result);
        setDone(null);
      } else {
        setDone(result);
        setPreview(null);
        onRestored?.();
      }
    } catch (callError) {
      setError(
        getApiErrorMessage(
          callError,
          dryRun ? "Impossibile calcolare cosa cambia." : "Ripristino dei ruoli non riuscito.",
        ),
      );
    } finally {
      setBusy(null);
      setConfirming(false);
    }
  }

  const toRestore = preview?.counts.toRestore ?? 0;

  return (
    <Card className="fa-admin-listone-restore" data-testid="admin-listone-restore">
      <CardHeader>
        <h2 className="fa-admin-listone-restore__title">
          Ripristina i ruoli cambiati da un aggiornamento
        </h2>
      </CardHeader>
      <CardBody>
        <p className="fa-admin-listone-restore__intro">
          Se un aggiornamento del listone ha cambiato il ruolo di calciatori già nelle rose, qui
          li riporti al ruolo che avevano prima dell'ora scelta. Il ruolo si ricostruisce dalle
          rose del fornitore salvate prima di quell'ora. Prima guardi cosa cambia, poi confermi.
        </p>
        <div className="fa-admin-listone-restore__form">
          <Input
            label="Ruoli com'erano prima del (ora di Roma)"
            name="admin-listone-restore-before"
            type="datetime-local"
            value={before}
            onChange={(event) => {
              setBefore(event.target.value);
              setPreview(null);
              setConfirming(false);
            }}
            data-testid="admin-listone-restore-before"
          />
          <Button
            type="button"
            variant="secondary"
            loading={busy === "preview"}
            disabled={busy !== null}
            onClick={() => void call(true)}
            data-testid="admin-listone-restore-preview"
          >
            Mostra cosa cambia
          </Button>
        </div>

        {error ? (
          <UiStatePanel
            state="error"
            title="Operazione non riuscita"
            message={error}
            testId="admin-listone-restore-error"
          />
        ) : null}

        {done ? (
          <UiStatePanel
            state="success"
            title="Ruoli ripristinati"
            message={`Ruoli ripristinati: ${done.counts.restored}. Rose ricalcolate: ${done.counts.rostersResynced}. Controlla le rose e la generazione del calendario.`}
            testId="admin-listone-restore-done"
          />
        ) : null}

        {preview ? (
          <div className="fa-admin-listone-restore__preview" data-testid="admin-listone-restore-result">
            <p data-testid="admin-listone-restore-summary">
              Da ripristinare: <strong>{preview.counts.toRestore}</strong> · Non ricostruibili:{" "}
              <strong>{preview.counts.notReconstructible}</strong> · Rose fuori quota con questi
              calciatori: ora <strong>{preview.counts.rostersOverQuotaNow}</strong>, dopo il
              ripristino <strong>{preview.counts.rostersOverQuotaAfter}</strong>
            </p>
            {preview.entries.length === 0 ? (
              <UiStatePanel
                state="empty"
                title="Niente da ripristinare"
                message={`Nessun ruolo cambiato dopo il ${formatRome(before)}.`}
                testId="admin-listone-restore-empty"
              />
            ) : (
              <Table compact data-testid="admin-listone-restore-table">
                <TableHead>
                  <TableRow>
                    <TableHeaderCell>Calciatore</TableHeaderCell>
                    <TableHeaderCell>Club</TableHeaderCell>
                    <TableHeaderCell>Ruolo ora</TableHeaderCell>
                    <TableHeaderCell>Ruolo di prima</TableHeaderCell>
                    <TableHeaderCell>In rosa nelle leghe</TableHeaderCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {preview.entries.map((entry) => (
                    <TableRow
                      key={entry.athleteId}
                      data-testid={`admin-listone-restore-row-${entry.athleteId}`}
                    >
                      <TableCell>{entry.name}</TableCell>
                      <TableCell>{entry.club ?? "—"}</TableCell>
                      <TableCell>
                        <RoleBadge role={entry.currentRole} />
                      </TableCell>
                      <TableCell>
                        <RoleBadge role={entry.restoredRole} />
                      </TableCell>
                      <TableCell>
                        {entry.inRosters.length > 0 ? entry.inRosters.join(", ") : "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
            {!confirming ? (
              <Button
                type="button"
                variant="primary"
                disabled={toRestore === 0 || busy !== null}
                onClick={() => setConfirming(true)}
                data-testid="admin-listone-restore-apply"
              >
                Ripristina
              </Button>
            ) : (
              <div
                className="fa-admin-listone-restore__confirm"
                role="alertdialog"
                aria-labelledby="admin-listone-restore-confirm-text"
                data-testid="admin-listone-restore-confirm"
              >
                <p id="admin-listone-restore-confirm-text">
                  Riporti {toRestore === 1 ? "1 calciatore" : `${toRestore} calciatori`} al ruolo
                  che avevano prima del {formatRome(before)}. Le rose che li hanno vengono
                  ricalcolate. I non ricostruibili restano come sono. Confermi?
                </p>
                <div className="fa-admin-listone-restore__actions">
                  <Button
                    type="button"
                    variant="danger"
                    loading={busy === "apply"}
                    onClick={() => void call(false)}
                    data-testid="admin-listone-restore-confirm-yes"
                  >
                    Sì, ripristina
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    disabled={busy !== null}
                    onClick={() => setConfirming(false)}
                    data-testid="admin-listone-restore-confirm-no"
                  >
                    Annulla
                  </Button>
                </div>
              </div>
            )}
          </div>
        ) : null}
      </CardBody>
    </Card>
  );
}
