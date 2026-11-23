import type { AthleteSeasonAverage } from "@fantappero/contracts";
import { formatSeasonAverage, marketValueLabel } from "./athleteValue";

/**
 * Media stagionale in una riga del mercato: verde «Media 6,45» se è della stagione in corso,
 * rossa «Media 6,12 · 25/26» se è quella della stagione scorsa (canvas «Proposte 1.3»).
 * Senza media non mostra nulla, oppure «—» con `emptyDash` (colonne di tabella).
 */
export function SeasonAverageBadge({
  average,
  emptyDash = false,
}: {
  average: AthleteSeasonAverage | null | undefined;
  emptyDash?: boolean;
}) {
  const display = formatSeasonAverage(average);
  if (!display) {
    return emptyDash ? (
      <span className="fa-season-avg fa-season-avg--none" data-tone="none">
        —
      </span>
    ) : null;
  }
  return (
    <span
      className={`fa-season-avg fa-season-avg--${display.tone}`}
      data-tone={display.tone}
      title={display.title}
    >
      <span className="fa-season-avg__label">Media </span>
      <span className="fa-season-avg__value">{display.text}</span>
    </span>
  );
}

/** «Valore 58»; niente se il calciatore non ha Valore. */
export function MarketValueBadge({ value }: { value: number | null | undefined }) {
  const label = marketValueLabel(value);
  if (!label) {
    return null;
  }
  return (
    <span className="fa-market-value" title="Valore di mercato: prezzo consigliato in crediti">
      {label}
    </span>
  );
}

/** Valore e media affiancati (vanno a capo su schermi stretti); niente se mancano entrambi. */
export function AthleteMarketTags({
  marketValue,
  seasonAverage,
  className,
  testId,
}: {
  marketValue?: number | null;
  seasonAverage?: AthleteSeasonAverage | null;
  className?: string;
  testId?: string;
}) {
  const hasValue = marketValueLabel(marketValue) !== null;
  const hasAverage = formatSeasonAverage(seasonAverage) !== null;
  if (!hasValue && !hasAverage) {
    return null;
  }
  return (
    <span className={className ? `fa-market-tags ${className}` : "fa-market-tags"} data-testid={testId}>
      <MarketValueBadge value={marketValue} />
      <SeasonAverageBadge average={seasonAverage} />
    </span>
  );
}

/** Riga gialla sotto il prezzo: «Valore 58: hai solo 40 crediti» o il suggerimento. */
export function MarketPriceHint({ children, testId }: { children: string; testId?: string }) {
  return (
    <p className="fa-market-hint" data-testid={testId}>
      {children}
    </p>
  );
}
