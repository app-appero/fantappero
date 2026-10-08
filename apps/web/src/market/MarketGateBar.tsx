import { Badge, Switch } from "@fantappero/ui";
import { useState } from "react";
import { marketGateHint, useMarketGate } from "./MarketGateContext";

/** Admin switch (and member status) for the league transfer window. */
export function MarketGateBar() {
  const { marketOpen, canManage, toggling, error, setOpen } = useMarketGate();
  const [infoOpen, setInfoOpen] = useState(false);
  const hint = marketGateHint(marketOpen);

  return (
    <div className="fa-market-gate" data-testid="market-gate-bar">
      <div className="fa-market-gate__main">
        <p className="fa-market-gate__title">
          Mercato{" "}
          <Badge variant={marketOpen ? "success" : "warning"}>
            {marketOpen ? "aperto" : "chiuso"}
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
        <p className="fa-market-gate__hint">{hint}</p>
      </div>
      {canManage ? (
        <Switch
          checked={marketOpen}
          onCheckedChange={(checked) => void setOpen(checked)}
          disabled={toggling}
          ariaLabel="Apri o chiudi il mercato"
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
