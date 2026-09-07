import type { FantasyRole, FantasyTeam } from "@fantappero/contracts";
import {
  Badge,
  Button,
  Input,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@fantappero/ui";
import { useEffect, useState } from "react";
import {
  compositionStatusLabel,
  compositionStatusVariant,
  ROLE_SECTION_ORDER,
  ROLE_SECTION_TITLE,
  ROSTER_PAGE_SIZE,
  roleBadgeVariant,
} from "./rosterHelpers";

type RosterSlot = FantasyTeam["slots"][number];

function PurchaseCreditsCell({
  slot,
  canEdit,
  busy,
  onUpdatePurchaseCredits,
}: {
  slot: RosterSlot;
  canEdit: boolean;
  busy: boolean;
  onUpdatePurchaseCredits?: (
    slotIndex: number,
    athleteId: string,
    purchaseCredits: number,
  ) => void | Promise<void>;
}) {
  const [draft, setDraft] = useState(String(slot.purchaseCredits ?? 0));

  useEffect(() => {
    setDraft(String(slot.purchaseCredits ?? 0));
  }, [slot.purchaseCredits]);

  if (!canEdit || !slot.athleteId || !onUpdatePurchaseCredits) {
    return <>{slot.purchaseCredits ?? "—"}</>;
  }

  const parsed = Number.parseInt(draft, 10);
  const isValid = Number.isFinite(parsed) && parsed >= 0;
  const isDirty = isValid && parsed !== (slot.purchaseCredits ?? 0);
  const athleteId = slot.athleteId;

  return (
    <div className="fa-roster-price-edit">
      <Input
        type="number"
        min={0}
        aria-label={`Prezzo acquisto ${slot.athleteName ?? "calciatore"}`}
        value={draft}
        disabled={busy}
        onChange={(event) => setDraft(event.target.value)}
        data-testid={`roster-purchase-credits-${athleteId}`}
      />
      {isDirty ? (
        <Button
          type="button"
          variant="secondary"
          disabled={busy}
          data-testid={`roster-purchase-credits-save-${athleteId}`}
          onClick={() => void onUpdatePurchaseCredits(slot.slotIndex, athleteId, parsed)}
        >
          Salva
        </Button>
      ) : null}
    </div>
  );
}

function RosterRoleTable({
  testId,
  title,
  badge,
  slots,
  countLabel,
  canEdit,
  adminBusy,
  onReleaseAthlete,
  onUpdatePurchaseCredits,
}: {
  testId: string;
  title: string;
  badge?: FantasyRole;
  slots: RosterSlot[];
  countLabel: string;
  canEdit: boolean;
  adminBusy: boolean;
  onReleaseAthlete: (athleteId: string) => void | Promise<void>;
  onUpdatePurchaseCredits?: (
    slotIndex: number,
    athleteId: string,
    purchaseCredits: number,
  ) => void | Promise<void>;
}) {
  const [page, setPage] = useState(0);
  const pageCount = Math.max(1, Math.ceil(slots.length / ROSTER_PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const pagedSlots = slots.slice(
    safePage * ROSTER_PAGE_SIZE,
    safePage * ROSTER_PAGE_SIZE + ROSTER_PAGE_SIZE,
  );

  return (
    <section className="fa-roster-role-section" data-testid={testId}>
      <h3 className="fa-roster-role-section__title">
        {badge ? <Badge variant={roleBadgeVariant(badge)}>{badge}</Badge> : null} {title}
        <span className="fa-roster-role-section__count">{countLabel}</span>
      </h3>
      {slots.length === 0 ? (
        <p className="fa-roster-role-section__empty">Nessun giocatore in questo ruolo.</p>
      ) : (
        <>
          <Table compact>
            <TableHead>
              <TableRow>
                <TableHeaderCell>Calciatore</TableHeaderCell>
                <TableHeaderCell>Club</TableHeaderCell>
                <TableHeaderCell>Crediti acquisto</TableHeaderCell>
                <TableHeaderCell>Slot</TableHeaderCell>
                {canEdit ? <TableHeaderCell>Azione</TableHeaderCell> : null}
              </TableRow>
            </TableHead>
            <TableBody>
              {pagedSlots.map((slot) => (
                <TableRow key={slot.id}>
                  <TableCell>{slot.athleteName ?? "Calciatore"}</TableCell>
                  <TableCell>{slot.clubName ?? "—"}</TableCell>
                  <TableCell>
                    <PurchaseCreditsCell
                      slot={slot}
                      canEdit={canEdit}
                      busy={adminBusy}
                      onUpdatePurchaseCredits={onUpdatePurchaseCredits}
                    />
                  </TableCell>
                  <TableCell>{slot.slotIndex + 1}</TableCell>
                  {canEdit ? (
                    <TableCell>
                      {slot.athleteId ? (
                        <Button
                          type="button"
                          variant="secondary"
                          disabled={adminBusy}
                          data-testid={`roster-admin-release-${slot.athleteId}`}
                          onClick={() => void onReleaseAthlete(slot.athleteId!)}
                        >
                          Rimuovi
                        </Button>
                      ) : null}
                    </TableCell>
                  ) : null}
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {pageCount > 1 ? (
            <div className="fa-roster-role-section__pagination" data-testid={`${testId}-pagination`}>
              <Button
                type="button"
                variant="ghost"
                disabled={safePage === 0}
                onClick={() => setPage((current) => Math.max(0, current - 1))}
              >
                Precedente
              </Button>
              <span>
                Pagina {safePage + 1} di {pageCount}
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
      )}
    </section>
  );
}

export function RosterFilledSummary({
  viewedTeam,
  filledByRole,
  canEdit,
  adminBusy,
  onReleaseAthlete,
  onUpdatePurchaseCredits,
}: {
  viewedTeam: FantasyTeam;
  filledByRole: Record<FantasyRole | "unknown", RosterSlot[]>;
  canEdit: boolean;
  adminBusy: boolean;
  onReleaseAthlete: (athleteId: string) => void | Promise<void>;
  onUpdatePurchaseCredits?: (
    slotIndex: number,
    athleteId: string,
    purchaseCredits: number,
  ) => void | Promise<void>;
}) {
  const compositionLimits = viewedTeam.composition?.limits;
  const roleLimit = (role: FantasyRole): number | null => {
    if (!compositionLimits) {
      return null;
    }
    if (role === "P") {
      return compositionLimits.goalkeepers;
    }
    if (role === "D") {
      return compositionLimits.defenders;
    }
    if (role === "C") {
      return compositionLimits.midfielders;
    }
    return compositionLimits.forwards;
  };

  return (
    <div data-testid="wireframe-roster-success">
      <p data-testid="roster-summary">
        {viewedTeam.name}: {viewedTeam.filledSlots}/{viewedTeam.rosterSize} giocatori
      </p>
      {viewedTeam.composition ? (
        <div data-testid="roster-composition">
          <p>
            Composizione:{" "}
            <Badge variant={compositionStatusVariant(viewedTeam.composition.status)}>
              <span data-testid="roster-composition-status">
                {compositionStatusLabel(viewedTeam.composition.status)}
              </span>
            </Badge>
          </p>
          <p data-testid="roster-composition-counts">
            {viewedTeam.composition.counts.P}/{viewedTeam.composition.limits.goalkeepers}P ·{" "}
            {viewedTeam.composition.counts.D}/{viewedTeam.composition.limits.defenders}D ·{" "}
            {viewedTeam.composition.counts.C}/{viewedTeam.composition.limits.midfielders}C ·{" "}
            {viewedTeam.composition.counts.A}/{viewedTeam.composition.limits.forwards}A ·{" "}
            {viewedTeam.composition.competitionCount} campionati
          </p>
          {viewedTeam.composition.issues.length > 0 ? (
            <ul data-testid="roster-composition-issues">
              {viewedTeam.composition.issues.map((issue) => (
                <li key={`${issue.code}-${issue.message}`}>{issue.message}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      <div className="fa-roster-role-tables" data-testid="roster-filled-table">
        {ROLE_SECTION_ORDER.map((role) => {
          const slots = filledByRole[role];
          const limit = roleLimit(role);
          return (
            <RosterRoleTable
              key={role}
              testId={`roster-filled-table-${role}`}
              title={ROLE_SECTION_TITLE[role]}
              badge={role}
              slots={slots}
              countLabel={`${slots.length}${limit != null ? `/${limit}` : ""}`}
              canEdit={canEdit}
              adminBusy={adminBusy}
              onReleaseAthlete={onReleaseAthlete}
              onUpdatePurchaseCredits={onUpdatePurchaseCredits}
            />
          );
        })}
        {filledByRole.unknown.length > 0 ? (
          <RosterRoleTable
            testId="roster-filled-table-unknown"
            title="Senza ruolo"
            slots={filledByRole.unknown}
            countLabel={String(filledByRole.unknown.length)}
            canEdit={canEdit}
            adminBusy={adminBusy}
            onReleaseAthlete={onReleaseAthlete}
            onUpdatePurchaseCredits={onUpdatePurchaseCredits}
          />
        ) : null}
      </div>
    </div>
  );
}
