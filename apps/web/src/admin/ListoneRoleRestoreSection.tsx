import type { AdminListoneRoleRestoreResult, FantasyRole } from "@fantappero/contracts";
import {
  DEFAULT_RESTORE_BEFORE,
  LISTONE_RESTORE_INTRO,
  LISTONE_RESTORE_TITLE,
  listoneRestoreConfirmText,
  listoneRestoreDoneMessage,
  listoneRestoreEmptyMessage,
  romeLocalToIso,
} from "@fantappero/contracts";
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

// L'ora di Roma e i testi stanno in `@fantappero/contracts`, gli stessi dell'app (1.5).
export { DEFAULT_RESTORE_BEFORE, romeLocalToIso };

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
        <h2 className="fa-admin-listone-restore__title">{LISTONE_RESTORE_TITLE}</h2>
      </CardHeader>
      <CardBody>
        <p className="fa-admin-listone-restore__intro">{LISTONE_RESTORE_INTRO}</p>
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
            message={listoneRestoreDoneMessage(done.counts)}
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
                message={listoneRestoreEmptyMessage(before)}
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
                        {entry.restoredClub && entry.restoredClub !== entry.club ? (
                          <small className="fa-admin-listone-restore__from">
                            {" "}
                            (rosa {entry.restoredClub})
                          </small>
                        ) : null}
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
                  {listoneRestoreConfirmText(toRestore, before)}
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
