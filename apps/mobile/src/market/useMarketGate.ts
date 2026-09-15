import { isMarketOpen } from "@fantappero/contracts";
import { useCallback, useEffect, useState } from "react";
import { fetchMarketGate, setMarketGate } from "../api/market";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";

export function useMarketGate() {
  const { accessToken, activeLeagueId, activeLeague, can, patchLeague } = useAuthSession();
  const canManage = can(["market:manage"]);
  const [marketOpen, setMarketOpen] = useState(() => isMarketOpen(activeLeague));
  const [toggling, setToggling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setMarketOpen(isMarketOpen(activeLeague));
  }, [activeLeague]);

  useEffect(() => {
    if (!accessToken || !activeLeagueId) {
      return;
    }
    let cancelled = false;
    void fetchMarketGate(accessToken, activeLeagueId)
      .then((gate) => {
        if (cancelled) {
          return;
        }
        setMarketOpen(gate.marketOpen);
        patchLeague(activeLeagueId, { marketOpen: gate.marketOpen });
      })
      .catch(() => {
        // Keep the last known value from the league summary.
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken, activeLeagueId, patchLeague]);

  const setOpen = useCallback(
    async (open: boolean) => {
      if (!canManage || !accessToken || !activeLeagueId) {
        return;
      }
      setToggling(true);
      setError(null);
      try {
        const gate = await setMarketGate(accessToken, activeLeagueId, { open });
        setMarketOpen(gate.marketOpen);
        patchLeague(activeLeagueId, { marketOpen: gate.marketOpen });
      } catch (cause) {
        setError(getApiErrorMessage(cause, "Impossibile aggiornare lo stato del mercato."));
      } finally {
        setToggling(false);
      }
    },
    [accessToken, activeLeagueId, canManage, patchLeague],
  );

  return { marketOpen, canManage, toggling, error, setOpen };
}
