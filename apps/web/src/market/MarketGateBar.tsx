import { MARKET_STATUS_BADGE_LABEL } from "@fantappero/contracts";
import { Badge, Switch } from "@fantappero/ui";
import { useState } from "react";
import { marketGateHint, useMarketGate } from "./MarketGateContext";

/** Admin switch (and member status) for the league transfer window. */
export function MarketGateBar() {
  const {
    marketOpen,
    canManage,
    toggling,
    error,
    setOpen,
    blockedNotice,
    statusBadge,
    switchLocked,
  } = useMarketGate();
  const [infoOpen, setInfoOpen] = useState(false);
  // A lega incompleta (decisione del 20/11) o a turno in corso (decisione del 21/11) il testo
  // spiega perché il mercato è fermo, e resta sempre visibile.
  const hint = blockedNotice ?? marketGateHint(marketOpen);

  return (
    <div className="fa-market-gate" data-testid="market-gate-bar">
      <div className="fa-market-gate__main">
        <p className="fa-market-gate__title" data-testid="market-gate-status">
          Mercato{" "}
          <Badge variant={statusBadge === "open" ? "success" : "warning"}>
            {MARKET_STATUS_BADGE_LABEL[statusBadge]}
          </Badge>
          <span className="fa-market-gate__info">
            <button
              type="button"
              className="fa-info-badge"
              aria-label="Informazioni sul mercato"
              aria-expanded={infoOpen}
              data-testid="market-gate-info"
              onClick={() => setInfoOpen((open) => !open)}
            >
              i
            </button>
            {infoOpen ? (
              <span className="fa-market-gate__popover" role="tooltip">
                {hint}
              </span>
            ) : null}
          </span>
        </p>
        {blockedNotice ? (
          <p
            className="fa-market-gate__notice"
            role="status"
            data-testid={statusBadge === "round_in_progress" ? "market-gate-round" : "market-gate-not-full"}
          >
            {blockedNotice}
          </p>
        ) : (
          <p className="fa-market-gate__hint">{hint}</p>
        )}
      </div>
      {canManage ? (
        <Switch
          checked={marketOpen}
          onCheckedChange={(checked) => void setOpen(checked)}
          disabled={toggling || switchLocked}
          ariaLabel="Mercato aperto"
          statusLabel={marketOpen ? "Aperto" : "Chiuso"}
          testId="market-gate-switch"
        />
      ) : null}
      {error ? (
        <p className="fa-market-gate__error" data-testid="market-gate-error">
          {error}
        </p>
      ) : null}
    </div>
  );
}
