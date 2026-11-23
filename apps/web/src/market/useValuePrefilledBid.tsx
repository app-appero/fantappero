import type { LeagueListoneEntry } from "@fantappero/contracts";
import { useCallback, useMemo, useState } from "react";
import { AthleteMarketTags, MarketPriceHint } from "./AthleteValueTags";
import {
  EMPTY_BID_DRAFT,
  OFFER_PRICE_MINIMUM,
  bidDraftForSelection,
  marketValuePrefill,
  offerPrefillHint,
  type BidDraft,
  type PricePrefill,
} from "./athleteValue";

/**
 * Modulo d'offerta di asta a buste e svincolati (1.3): scelto il calciatore, l'offerta parte
 * dal suo Valore (o dai crediti rimasti, se sono meno) e resta modificabile. Il minimo resta
 * 1 credito, come oggi. Non vale per l'asta live, dove il Valore è solo mostrato.
 */
export function useValuePrefilledBid(entries: readonly LeagueListoneEntry[], balance: number | null) {
  const [athleteId, setAthleteId] = useState("");
  const [draft, setDraft] = useState<BidDraft>(EMPTY_BID_DRAFT);

  const entryById = useMemo(() => {
    const map = new Map<string, LeagueListoneEntry>();
    for (const entry of entries) {
      map.set(entry.athleteId, entry);
    }
    return map;
  }, [entries]);

  const prefillFor = useCallback(
    (id: string): PricePrefill | null => {
      const entry = id ? entryById.get(id) : undefined;
      return entry
        ? marketValuePrefill({
            marketValue: entry.marketValue,
            remainingCredits: balance,
            minimum: OFFER_PRICE_MINIMUM,
          })
        : null;
    },
    [balance, entryById],
  );

  const selectAthlete = useCallback(
    (id: string) => {
      setAthleteId(id);
      setDraft((current) => bidDraftForSelection(current, prefillFor(id)));
    },
    [prefillFor],
  );

  const changeAmount = useCallback((amount: string) => {
    setDraft({ amount, fromValue: false });
  }, []);

  const reset = useCallback(() => {
    setAthleteId("");
    setDraft(EMPTY_BID_DRAFT);
  }, []);

  const selected = athleteId ? (entryById.get(athleteId) ?? null) : null;
  const prefill = prefillFor(athleteId);

  return {
    athleteId,
    amount: draft.amount,
    /** L'offerta è ancora quella proposta dal Valore. */
    fromValue: draft.fromValue,
    selected,
    prefill,
    selectAthlete,
    changeAmount,
    reset,
  };
}

/** Sotto il campo offerta: il calciatore scelto con Valore e media, e la riga sul prezzo. */
export function OfferValueSummary({
  selected,
  prefill,
  testId,
}: {
  selected: LeagueListoneEntry | null;
  prefill: PricePrefill | null;
  testId: string;
}) {
  if (!selected) {
    return null;
  }
  const hint = offerPrefillHint(prefill);
  return (
    <div className="fa-market-offer" data-testid={testId}>
      <p className="fa-market-offer__selected">
        <strong>{selected.canonicalName}</strong>
        {selected.clubName ? <span className="fa-market-offer__club"> · {selected.clubName}</span> : null}
      </p>
      <AthleteMarketTags marketValue={selected.marketValue} seasonAverage={selected.seasonAverage} />
      {hint ? <MarketPriceHint testId={`${testId}-hint`}>{hint}</MarketPriceHint> : null}
    </div>
  );
}
