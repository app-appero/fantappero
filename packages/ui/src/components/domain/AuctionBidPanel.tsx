import type { ChangeEvent, FormEvent, ReactNode } from "react";
import { Button } from "../Button.js";
import { Card, CardBody, CardFooter, CardHeader } from "../Card.js";
import { Input } from "../Input.js";
import { Select, type SelectOption } from "../Select.js";

export type AuctionBidPanelProps = {
  title: string;
  budgetLabel: string;
  budgetValue: string;
  playerLabel: string;
  playerPlaceholder: string;
  bidLabel: string;
  bidPlaceholder: string;
  submitLabel: string;
  statusLabel: string;
  statusMessage: string;
  testId?: string;
  /** Controlled player field — omit to keep the panel purely presentational. */
  playerValue?: string;
  onPlayerChange?: (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => void;
  /** Renders the player field as a <select> of these options instead of free text. */
  playerOptions?: SelectOption[];
  /** Controlled bid amount field — omit to keep the panel purely presentational. */
  bidValue?: string;
  onBidChange?: (event: ChangeEvent<HTMLInputElement>) => void;
  /** Provided to make the panel a real, submittable form. */
  onSubmit?: (event: FormEvent<HTMLFormElement>) => void;
  submitting?: boolean;
  disabled?: boolean;
  /** Extra field rendered between the bid amount and the status line (e.g. release-athlete picker for waivers). */
  extraField?: ReactNode;
  errorMessage?: string;
};

/** Sealed-bid auction/waiver panel — controlled form when handlers are provided, presentational otherwise (EPUI-04). */
export function AuctionBidPanel({
  title,
  budgetLabel,
  budgetValue,
  playerLabel,
  playerPlaceholder,
  bidLabel,
  bidPlaceholder,
  submitLabel,
  statusLabel,
  statusMessage,
  testId = "auction-bid-panel",
  playerValue,
  onPlayerChange,
  playerOptions,
  bidValue,
  onBidChange,
  onSubmit,
  submitting = false,
  disabled = false,
  extraField,
  errorMessage,
}: AuctionBidPanelProps) {
  const body = (
    <>
      <p className="fa-auction-panel__budget">
        <span className="fa-auction-panel__budget-label">{budgetLabel}</span>
        <strong>{budgetValue}</strong>
      </p>
      {playerOptions ? (
        <Select
          label={playerLabel}
          placeholder={playerPlaceholder}
          name="auction-player"
          options={playerOptions}
          value={playerValue}
          onChange={onPlayerChange}
          disabled={disabled}
        />
      ) : (
        <Input
          label={playerLabel}
          placeholder={playerPlaceholder}
          name="auction-player"
          value={playerValue}
          onChange={onPlayerChange}
          disabled={disabled}
        />
      )}
      <Input
        label={bidLabel}
        placeholder={bidPlaceholder}
        name="auction-bid"
        type="number"
        value={bidValue}
        onChange={onBidChange}
        disabled={disabled}
      />
      {extraField}
      {errorMessage ? (
        <p className="fa-auction-panel__error" role="alert">
          {errorMessage}
        </p>
      ) : null}
      <p className="fa-auction-panel__status">
        <span className="fa-auction-panel__status-label">{statusLabel}</span>
        {statusMessage}
      </p>
    </>
  );

  if (onSubmit) {
    return (
      <form data-testid={testId} onSubmit={onSubmit}>
        <Card>
          <CardHeader>{title}</CardHeader>
          <CardBody>{body}</CardBody>
          <CardFooter>
            <Button type="submit" variant="primary" disabled={disabled || submitting}>
              {submitting ? "Invio…" : submitLabel}
            </Button>
          </CardFooter>
        </Card>
      </form>
    );
  }

  return (
    <Card data-testid={testId}>
      <CardHeader>{title}</CardHeader>
      <CardBody>{body}</CardBody>
      <CardFooter>
        <Button variant="primary" disabled={disabled}>
          {submitLabel}
        </Button>
      </CardFooter>
    </Card>
  );
}
