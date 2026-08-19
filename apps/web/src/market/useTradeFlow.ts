import type {
  CounterTradeProposalRequest,
  CreateTradeProposalRequest,
  TradeProposal,
} from "@fantappero/contracts";
import { useCallback, useEffect, useState } from "react";
import {
  acceptTradeProposal,
  approveTradeProposal,
  cancelTradeProposal,
  counterTradeProposal,
  createTradeProposal,
  fetchTradeProposals,
  rejectTradeProposal,
  rejectTradeProposalAsAdmin,
} from "../api/market";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";

export interface UseTradeFlowOptions {
  leagueId: string | null;
  active: boolean;
}

/** Trade proposal lifecycle: create/list/cancel/accept/reject/counter (EP08-05/06). */
export function useTradeFlow({ leagueId, active }: UseTradeFlowOptions) {
  const [proposals, setProposals] = useState<TradeProposal[]>([]);
  const [loading, setLoading] = useState(active);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const [actionError, setActionError] = useState<string | null>(null);
  const [actionPendingId, setActionPendingId] = useState<string | null>(null);

  const requireToken = useCallback((): string | null => {
    const stored = loadStoredSession();
    return stored?.accessToken ?? null;
  }, []);

  const loadProposals = useCallback(async () => {
    if (!active || !leagueId) {
      setLoading(false);
      setProposals([]);
      setLoadError(null);
      return;
    }
    const accessToken = requireToken();
    if (!accessToken) {
      setLoading(false);
      setLoadError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      const result = await fetchTradeProposals(accessToken, leagueId);
      setProposals(result.proposals);
    } catch (error) {
      setProposals([]);
      setLoadError(getApiErrorMessage(error, "Impossibile caricare le proposte di scambio."));
    } finally {
      setLoading(false);
    }
  }, [active, leagueId, requireToken]);

  useEffect(() => {
    void loadProposals();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, leagueId]);

  const createProposal = useCallback(
    async (body: CreateTradeProposalRequest) => {
      if (!leagueId) {
        return;
      }
      const accessToken = requireToken();
      if (!accessToken) {
        setCreateError("Sessione non disponibile. Accedi di nuovo.");
        return;
      }
      setCreating(true);
      setCreateError(null);
      try {
        await createTradeProposal(accessToken, leagueId, body);
        await loadProposals();
      } catch (error) {
        setCreateError(getApiErrorMessage(error, "Impossibile inviare la proposta."));
      } finally {
        setCreating(false);
      }
    },
    [leagueId, loadProposals, requireToken],
  );

  function withProposalAction(
    action: (accessToken: string, leagueId: string, proposalId: string) => Promise<TradeProposal>,
    fallbackMessage: string,
  ) {
    return async (proposalId: string) => {
      if (!leagueId) {
        return;
      }
      const accessToken = requireToken();
      if (!accessToken) {
        setActionError("Sessione non disponibile. Accedi di nuovo.");
        return;
      }
      setActionPendingId(proposalId);
      setActionError(null);
      try {
        await action(accessToken, leagueId, proposalId);
        await loadProposals();
      } catch (error) {
        setActionError(getApiErrorMessage(error, fallbackMessage));
      } finally {
        setActionPendingId(null);
      }
    };
  }

  const cancelProposal = withProposalAction(cancelTradeProposal, "Impossibile annullare la proposta.");
  const acceptProposal = withProposalAction(acceptTradeProposal, "Impossibile accettare la proposta.");
  const rejectProposal = withProposalAction(rejectTradeProposal, "Impossibile rifiutare la proposta.");
  const approveProposal = withProposalAction(
    approveTradeProposal,
    "Impossibile approvare la proposta.",
  );
  const rejectProposalAsAdmin = withProposalAction(
    rejectTradeProposalAsAdmin,
    "Impossibile rifiutare la proposta.",
  );

  const counterProposal = useCallback(
    async (proposalId: string, body: CounterTradeProposalRequest) => {
      if (!leagueId) {
        return;
      }
      const accessToken = requireToken();
      if (!accessToken) {
        setActionError("Sessione non disponibile. Accedi di nuovo.");
        return;
      }
      setActionPendingId(proposalId);
      setActionError(null);
      try {
        await counterTradeProposal(accessToken, leagueId, proposalId, body);
        await loadProposals();
      } catch (error) {
        setActionError(getApiErrorMessage(error, "Impossibile inviare la controproposta."));
      } finally {
        setActionPendingId(null);
      }
    },
    [leagueId, loadProposals, requireToken],
  );

  return {
    proposals,
    loading,
    loadError,
    reload: loadProposals,
    createProposal,
    creating,
    createError,
    cancelProposal,
    acceptProposal,
    rejectProposal,
    counterProposal,
    approveProposal,
    rejectProposalAsAdmin,
    actionPendingId,
    actionError,
  };
}
