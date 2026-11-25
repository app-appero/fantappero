import type { ReplacementBanner, TradeShortfallWarning } from "@fantappero/contracts";
import { REPLACEMENT_AUTO_LINEUP_NOTE } from "@fantappero/contracts";
import { Button } from "@fantappero/ui";

/** Triangolo d'avviso dei riquadri arancioni. */
function WarningIcon() {
  return (
    <svg
      className="fa-shortfall__icon"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
      <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
    </svg>
  );
}

/**
 * Riquadro arancione «Dopo lo scambio avrai 34/35» (1.5): nella conferma di chi accetta, di chi
 * propone e dell'amministratore che approva. I testi vengono da `tradeShortfallWarning`.
 */
export function TradeShortfallNotice({
  warning,
  testId = "trade-shortfall-warning",
}: {
  warning: TradeShortfallWarning;
  testId?: string;
}) {
  return (
    <div className="fa-shortfall" role="note" data-testid={testId}>
      <WarningIcon />
      <div className="fa-shortfall__text">
        <p className="fa-shortfall__title">{warning.title}</p>
        <p className="fa-shortfall__body">{warning.body}</p>
      </div>
    </div>
  );
}

/**
 * Riquadro «Rosa incompleta: 34/35» in Rosa e Formazione finché manca il sostituto, con il
 * pulsante che riapre la scelta. A turno in corso dice quando si potrà scegliere.
 */
export function RosterShortfallBanner({
  banner,
  onChoose,
  testId = "roster-shortfall-banner",
}: {
  banner: ReplacementBanner;
  onChoose: () => void;
  testId?: string;
}) {
  return (
    <div className="fa-shortfall fa-shortfall--banner" role="alert" data-testid={testId}>
      <WarningIcon />
      <div className="fa-shortfall__text">
        <p className="fa-shortfall__title">{banner.title}</p>
        <p className="fa-shortfall__body">{banner.body}</p>
        {banner.blockedMessage ? (
          <p className="fa-shortfall__body" data-testid={`${testId}-blocked`}>
            {banner.blockedMessage}
          </p>
        ) : null}
        <Button type="button" variant="primary" size="sm" onClick={onChoose} data-testid={`${testId}-choose`}>
          {banner.action}
        </Button>
      </div>
    </div>
  );
}

/** Nota sotto «Salva formazione» (disattivato) finché manca il sostituto. */
export function ReplacementAutoLineupNote() {
  return (
    <p className="fa-field__hint fa-shortfall__note" data-testid="formation-replacement-note">
      {REPLACEMENT_AUTO_LINEUP_NOTE}
    </p>
  );
}
