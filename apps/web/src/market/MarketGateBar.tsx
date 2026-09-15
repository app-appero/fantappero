import { Badge, Switch } from "@fantappero/ui";
import { marketGateHint, useMarketGate } from "./MarketGateContext";

/** Admin switch (and member status) for the league transfer window. */
export function MarketGateBar() {
  const { marketOpen, canManage, toggling, error, setOpen } = useMarketGate();

  return (
    <div className="fa-market-gate" data-testid="market-gate-bar">
      <div className="fa-market-gate__copy">
        <p className="fa-market-gate__title">
          Mercato{" "}
          <Badge variant={marketOpen ? "success" : "warning"}>
            {marketOpen ? "aperto" : "chiuso"}
          </Badge>
        </p>
        <p className="fa-market-gate__hint">{marketGateHint(marketOpen)}</p>
        {error ? (
          <p className="fa-market-gate__hint" data-testid="market-gate-error">
            {error}
          </p>
        ) : null}
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
    </div>
  );
}
