import type { ReplacementBanner, TradeAfterNotice } from "@fantappero/contracts";
import { REPLACEMENT_AUTO_LINEUP_NOTE } from "@fantappero/contracts";
import { Button } from "@fantappero/ui";

/** Cerchio con la «i» dei riquadri informativi gialli (ruoli sotto quota). */
function InfoIcon() {
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
      <circle cx="12" cy="12" r="10" />
      <path d="M12 16v-4" />
      <path d="M12 8h.01" />
    </svg>
  );
}

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
 * propone e dell'amministratore che approva. Sotto, se servono, l'avviso dei crediti che non
 * bastano e la riga dei ruoli sotto quota; con i soli ruoli sotto quota il riquadro è giallo e più
 * leggero (`info`). I testi vengono da `tradeAfterNotice`.
 */
export function TradeShortfallNotice({
  notice,
  testId = "trade-shortfall-warning",
}: {
  notice: TradeAfterNotice;
  testId?: string;
}) {
  const info = notice.tone === "info";
  return (
    <div className={info ? "fa-shortfall fa-shortfall--info" : "fa-shortfall"} role="note" data-testid={testId}>
      {info ? <InfoIcon /> : <WarningIcon />}
      <div className="fa-shortfall__text">
        {notice.title ? <p className="fa-shortfall__title">{notice.title}</p> : null}
        {notice.body ? <p className="fa-shortfall__body">{notice.body}</p> : null}
        {notice.creditsWarning ? (
          <p className="fa-shortfall__body fa-shortfall__credits" data-testid={`${testId}-credits`}>
            {notice.creditsWarning}
          </p>
        ) : null}
        {notice.quotaNote ? (
          <p className="fa-shortfall__body" data-testid={`${testId}-quota`}>
            {notice.quotaNote}
          </p>
        ) : null}
      </div>
    </div>
  );
}

/**
 * Riquadro informativo giallo in Rosa: «Ruoli sotto quota: 9 Centrocampisti su 11. Puoi
 * completarli con uno scambio o agli svincolati.» Non blocca niente; con sostituti da scegliere si
 * vede il riquadro dei sostituti al suo posto.
 */
export function RosterQuotaNotice({ text, testId = "roster-under-quota" }: { text: string; testId?: string }) {
  return (
    <div className="fa-shortfall fa-shortfall--info fa-shortfall--banner" role="note" data-testid={testId}>
      <InfoIcon />
      <div className="fa-shortfall__text">
        <p className="fa-shortfall__body">{text}</p>
      </div>
    </div>
  );
}

/** Riquadro in alto nella finestra «Scegli il sostituto» quando nessun libero è alla portata. */
export function ReplacementUnaffordableNotice({ text }: { text: string }) {
  return (
    <div className="fa-shortfall" role="note" data-testid="replacement-unaffordable">
      <WarningIcon />
      <div className="fa-shortfall__text">
        <p className="fa-shortfall__body">{text}</p>
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
