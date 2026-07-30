import { Button } from "../Button.js";
import { Card, CardBody, CardFooter, CardHeader } from "../Card.js";
import { Input } from "../Input.js";

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
};

/** Presentational sealed-bid auction panel (wireframe / EPUI-04). */
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
}: AuctionBidPanelProps) {
  return (
    <Card data-testid={testId}>
      <CardHeader>{title}</CardHeader>
      <CardBody>
        <p className="fa-auction-panel__budget">
          <span className="fa-auction-panel__budget-label">{budgetLabel}</span>
          <strong>{budgetValue}</strong>
        </p>
        <Input label={playerLabel} placeholder={playerPlaceholder} name="auction-player" />
        <Input
          label={bidLabel}
          placeholder={bidPlaceholder}
          name="auction-bid"
          type="number"
        />
        <p className="fa-auction-panel__status">
          <span className="fa-auction-panel__status-label">{statusLabel}</span>
          {statusMessage}
        </p>
      </CardBody>
      <CardFooter>
        <Button variant="primary">{submitLabel}</Button>
      </CardFooter>
    </Card>
  );
}
