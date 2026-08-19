import type { MarketHistoryEntry, MarketHistoryFilters } from "@fantappero/contracts";
import { useCallback, useEffect, useState } from "react";
import { fetchMarketHistory } from "../api/market";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";

export interface UseMarketHistoryOptions {
  leagueId: string | null;
  active: boolean;
}

const DEFAULT_PAGE_SIZE = 20;

/** Filterable, paginated market history feed (EP08-08 / FR-MKT-04). */
export function useMarketHistory({ leagueId, active }: UseMarketHistoryOptions) {
  const [items, setItems] = useState<MarketHistoryEntry[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(active);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [category, setCategory] = useState<MarketHistoryFilters["category"] | "">("");
  const [fantasyTeamId, setFantasyTeamId] = useState("");

  const load = useCallback(
    async (targetPage: number) => {
      if (!active || !leagueId) {
        setLoading(false);
        setItems([]);
        setLoadError(null);
        return;
      }
      const stored = loadStoredSession();
      if (!stored?.accessToken) {
        setLoading(false);
        setLoadError("Sessione non disponibile. Accedi di nuovo.");
        return;
      }
      setLoading(true);
      setLoadError(null);
      try {
        const result = await fetchMarketHistory(stored.accessToken, leagueId, {
          category: category || undefined,
          fantasyTeamId: fantasyTeamId || undefined,
          page: targetPage,
          pageSize: DEFAULT_PAGE_SIZE,
        });
        setItems(result.items);
        setPage(result.page);
        setTotalPages(result.totalPages);
        setTotal(result.total);
      } catch (error) {
        setItems([]);
        setLoadError(getApiErrorMessage(error, "Impossibile caricare lo storico mercato."));
      } finally {
        setLoading(false);
      }
    },
    [active, category, fantasyTeamId, leagueId],
  );

  useEffect(() => {
    void load(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, leagueId, category, fantasyTeamId]);

  return {
    items,
    page,
    totalPages,
    total,
    loading,
    loadError,
    category,
    setCategory,
    fantasyTeamId,
    setFantasyTeamId,
    goToPage: (target: number) => void load(target),
  };
}
