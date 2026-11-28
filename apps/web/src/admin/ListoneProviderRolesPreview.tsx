import type { AdminListoneProviderRolesResult } from "@fantappero/contracts";
import {
  LISTONE_ROLE_PREVIEW_CANCEL_LABEL,
  LISTONE_ROLE_PREVIEW_CONFIRM_LABEL,
  LISTONE_ROLE_PREVIEW_INTRO,
  LISTONE_ROLE_PREVIEW_TITLE,
  listoneRoleChangesLabel,
} from "@fantappero/contracts";
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  UiStatePanel,
} from "@fantappero/ui";
import { useState } from "react";
import { updateAdminListoneRolesFromProvider } from "../api/admin";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";

type Props = {
  preview: AdminListoneProviderRolesResult;
  /** Dopo la conferma (ruoli applicati) o l'annullamento. */
  onDone: (applied: AdminListoneProviderRolesResult | null) => void;
};

/**
 * Anteprima di «Aggiorna anche i ruoli dal fornitore»: chi cambierebbe ruolo, dove è in rosa e
 * quante rose andrebbero fuori quota. I ruoli cambiano solo con «Conferma i nuovi ruoli».
 */
export function ListoneProviderRolesPreview({ preview, onDone }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const changes = preview.counts.changes;

  async function confirm() {
    const session = loadStoredSession();
    if (!session?.accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const applied = await updateAdminListoneRolesFromProvider(session.accessToken, {
        seasonYear: preview.seasonYear,
        dryRun: false,
        athleteIds: preview.entries.map((entry) => entry.athleteId),
      });
      onDone(applied);
    } catch (confirmError) {
      setError(getApiErrorMessage(confirmError, "Aggiornamento dei ruoli non riuscito."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="fa-admin-listone-restore" data-testid="admin-listone-role-preview">
      <CardHeader>
        <h2 className="fa-admin-listone-restore__title">{LISTONE_ROLE_PREVIEW_TITLE}</h2>
      </CardHeader>
      <CardBody>
        <p data-testid="admin-listone-role-preview-summary">
          {listoneRoleChangesLabel(changes)} · Rose fuori quota con questi calciatori: ora{" "}
          <strong>{preview.counts.rostersOverQuotaNow}</strong>, con i nuovi ruoli{" "}
          <strong>{preview.counts.rostersOverQuotaAfter}</strong>
        </p>
        <p className="fa-admin-listone-restore__intro">{LISTONE_ROLE_PREVIEW_INTRO}</p>
        <Table compact data-testid="admin-listone-role-preview-table">
          <TableHead>
            <TableRow>
              <TableHeaderCell>Calciatore</TableHeaderCell>
              <TableHeaderCell>Club</TableHeaderCell>
              <TableHeaderCell>Ruolo ora</TableHeaderCell>
              <TableHeaderCell>Nuovo ruolo</TableHeaderCell>
              <TableHeaderCell>In rosa nelle leghe</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {preview.entries.map((entry) => (
              <TableRow
                key={entry.athleteId}
                data-testid={`admin-listone-role-preview-row-${entry.athleteId}`}
              >
                <TableCell>{entry.name}</TableCell>
                <TableCell>{entry.club ?? "—"}</TableCell>
                <TableCell>
                  <Badge variant="accent">{entry.currentRole}</Badge>
                </TableCell>
                <TableCell>
                  <Badge variant="warning">{entry.newRole}</Badge>
                </TableCell>
                <TableCell>
                  {entry.inRosters.length > 0 ? entry.inRosters.join(", ") : "—"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {error ? (
          <UiStatePanel
            state="error"
            title="Ruoli non aggiornati"
            message={error}
            testId="admin-listone-role-preview-error"
          />
        ) : null}
        <div className="fa-admin-listone-restore__actions">
          <Button
            type="button"
            variant="danger"
            loading={busy}
            onClick={() => void confirm()}
            data-testid="admin-listone-role-preview-confirm"
          >
            {LISTONE_ROLE_PREVIEW_CONFIRM_LABEL}
          </Button>
          <Button
            type="button"
            variant="ghost"
            disabled={busy}
            onClick={() => onDone(null)}
            data-testid="admin-listone-role-preview-cancel"
          >
            {LISTONE_ROLE_PREVIEW_CANCEL_LABEL}
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}
