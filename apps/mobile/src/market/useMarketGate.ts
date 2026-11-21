import { isMarketOpen, type MarketGate } from "@fantappero/contracts";
import { useCallback, useEffect, useRef, useState } from "react";
import { fetchMarketGate, setMarketGate } from "../api/market";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";
import {
  isMarketActive,
  marketBlockedNotice,
  marketClosedTitle,
  marketNotFullNotice,
  marketRoundInProgress,
  marketStatusBadge,
  marketSwitchLocked,
} from "./marketGateNotice";

export type MarketGateHandle = ReturnType<typeof useMarketGate>;

export function useMarketGate({ reloadToken = 0 }: { reloadToken?: number } = {}) {
  const { accessToken, activeLeagueId, activeLeague, can, patchLeague } = useAuthSession();
  const canManage = can(["market:manage"]);
  const [gate, setGate] = useState<MarketGate>(() => ({ marketOpen: isMarketOpen(activeLeague) }));
  const [toggling, setToggling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastLeagueIdRef = useRef(activeLeagueId);

  useEffect(() => {
    if (lastLeagueIdRef.current === activeLeagueId) {
      return;
    }
    lastLeagueIdRef.current = activeLeagueId;
    setGate({ marketOpen: isMarketOpen(activeLeague) });
  }, [activeLeague, activeLeagueId]);

  useEffect(() => {
    if (!accessToken || !activeLeagueId) {
      return;
    }
    let cancelled = false;
    void fetchMarketGate(accessToken, activeLeagueId)
      .then((next) => {
        if (cancelled) {
          return;
        }
        setGate(next);
        patchLeague(activeLeagueId, { marketOpen: next.marketOpen });
      })
      .catch(() => {
        // Keep the last known value from the league summary.
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken, activeLeagueId, patchLeague, reloadToken]);

  const setOpen = useCallback(
    async (open: boolean) => {
      if (!canManage || !accessToken || !activeLeagueId) {
        return;
      }
      setToggling(true);
      setError(null);
      try {
        const next = await setMarketGate(accessToken, activeLeagueId, { open });
        setGate(next);
        patchLeague(activeLeagueId, { marketOpen: next.marketOpen });
      } catch (cause) {
        setError(getApiErrorMessage(cause, "Impossibile aggiornare lo stato del mercato."));
      } finally {
        setToggling(false);
      }
    },
    [accessToken, activeLeagueId, canManage, patchLeague],
  );

  return {
    /** Interruttore dell'amministratore. */
    marketOpen: gate.marketOpen,
    /**
     * Interruttore acceso e lega al completo (decisione del 20/11): rosa, aste e scambi del
     * partecipante. Le operazioni dell'amministratore sulle rose non dipendono né da questo
     * né dall'interruttore: si fermano solo a turno in corso.
     */
    marketActive: isMarketActive(gate),
    leagueFull: gate.leagueFull !== false,
    /**
     * «Il mercato si apre quando la lega è al completo (5/8).», con «· 1 invito in attesa» se ci
     * sono inviti nominativi in attesa; `null` a lega al completo.
     */
    notFullNotice: marketNotFullNotice(gate),
    /** Inviti nominativi in attesa: tengono un posto, ma la lega è al completo solo con gli iscritti. */
    pendingInviteCount: gate.pendingInviteCount ?? 0,
    /**
     * Turno in corso (dal primo blocco all'omologazione): rosa, aste e scambi fermi per tutti,
     * amministratore compreso (decisione di Rosario del 21/11).
     */
    roundInProgress: marketRoundInProgress(gate),
    /** Stato del riquadro: «Mercato aperto», «Mercato chiuso», «Mercato fermo: turno in corso». */
    statusBadge: marketStatusBadge(gate),
    /** Motivo sempre visibile del mercato fermo (lega incompleta o turno in corso), altrimenti `null`. */
    blockedNotice: marketBlockedNotice(gate),
    /** Titolo degli avvisi di mercato fermo: «Mercato chiuso» o «Mercato fermo: turno in corso». */
    closedTitle: marketClosedTitle(gate),
    /** A lega incompleta l'interruttore spento non si accende (spegnerlo resta possibile). */
    switchLocked: marketSwitchLocked(gate),
    canManage,
    toggling,
    error,
    setOpen,
  };
}
