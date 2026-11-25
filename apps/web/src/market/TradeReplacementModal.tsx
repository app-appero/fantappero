import {
  type FantasyRole,
  type TradeReplacementCandidate,
  type TradeReplacementOrder,
  type TradeReplacementStatus,
  REPLACEMENT_CANCEL_LABEL,
  REPLACEMENT_CONFIRM_LABEL,
  REPLACEMENT_EMPTY_LIST,
  REPLACEMENT_LATER_LABEL,
  REPLACEMENT_LATER_NOTE,
  REPLACEMENT_ORDER_OPTIONS,
  REPLACEMENT_SEARCH_PLACEHOLDER,
  REPLACEMENT_SHEET_TITLE,
  REPLACEMENT_TOO_EXPENSIVE,
  replacementChips,
  replacementConfirmNote,
  replacementConfirmTitle,
  replacementCreditRows,
  replacementDoneBanner,
  replacementIntro,
  replacementPurchasedMessage,
  replacementRoles,
  replacementTakeLabel,
  roleSingularLabel,
} from "@fantappero/contracts";
import { Button, Input, Modal, Select, UiStatePanel, useOptionalToast } from "@fantappero/ui";
import { useEffect, useMemo, useState } from "react";
import { buyTradeReplacement, fetchTradeReplacementCandidates } from "../api/market";
import { getApiErrorMessage } from "../api/client";
import { loadStoredSession } from "../auth/sessionStorage";
import { MarketValueBadge, SeasonAverageBadge } from "./AthleteValueTags";

const SEARCH_DEBOUNCE_MS = 250;

/**
 * Finestra «Scegli il sostituto» (1.5): dopo uno scambio che ha lasciato la rosa sotto la misura
 * la squadra sceglie un calciatore libero del ruolo che manca e lo paga il suo Valore. Prima
 * l'elenco dei liberi (ricerca e ordine per Valore), poi la conferma con il conto dei crediti. Con
 * due posti da riempire si sceglie uno alla volta. «Più tardi» chiude: i riquadri in Rosa e
 * Formazione restano.
 */
export function TradeReplacementModal({
  open,
  leagueId,
  status,
  onClose,
  onStatusChange,
}: {
  open: boolean;
  leagueId: string | null;
  status: TradeReplacementStatus | null;
  onClose: () => void;
  onStatusChange: (next: TradeReplacementStatus) => void;
}) {
  const toast = useOptionalToast();
  const roles = useMemo(() => replacementRoles(status?.missingRoles), [status]);
  const [role, setRole] = useState<FantasyRole | null>(null);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [order, setOrder] = useState<TradeReplacementOrder>("valore");
  const [candidates, setCandidates] = useState<TradeReplacementCandidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [target, setTarget] = useState<TradeReplacementCandidate | null>(null);
  const [buying, setBuying] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);

  const activeRole: FantasyRole | null = role && roles.includes(role) ? role : (roles[0] ?? null);
  const blocked = Boolean(status?.blockedMessage);

  useEffect(() => {
    if (!open) {
      setTarget(null);
      setError(null);
      setSearch("");
      setDebouncedSearch("");
    }
  }, [open]);

  useEffect(() => {
    const handle = window.setTimeout(() => setDebouncedSearch(search), SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(handle);
  }, [search]);

  useEffect(() => {
    if (!open || !leagueId || !activeRole) {
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    let cancelled = false;
    setLoading(true);
    void fetchTradeReplacementCandidates(stored.accessToken, leagueId, {
      role: activeRole,
      search: debouncedSearch,
      order,
    })
      .then((list) => {
        if (!cancelled) {
          setCandidates(list.candidates);
        }
      })
      .catch((cause) => {
        if (!cancelled) {
          setCandidates([]);
          setError(getApiErrorMessage(cause, "Impossibile caricare i calciatori liberi."));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [activeRole, debouncedSearch, leagueId, open, order, reloadToken]);

  async function confirmPurchase() {
    if (!target || !leagueId || buying) {
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setBuying(true);
    setError(null);
    try {
      const purchase = await buyTradeReplacement(stored.accessToken, leagueId, target.athleteId);
      toast?.push({ title: "Sostituto preso", message: replacementPurchasedMessage(purchase), variant: "success" });
      onStatusChange(purchase.status);
      setTarget(null);
      setReloadToken((value) => value + 1);
      if (purchase.status.pending.length === 0) {
        onClose();
      }
    } catch (cause) {
      // Es. il calciatore l'ha appena preso un'altra squadra: si torna all'elenco aggiornato.
      setError(getApiErrorMessage(cause, "Impossibile prendere il calciatore."));
      setTarget(null);
      setReloadToken((value) => value + 1);
    } finally {
      setBuying(false);
    }
  }

  if (!status) {
    return null;
  }
  const done = replacementDoneBanner(status);

  if (target && activeRole) {
    return (
      <Modal
        open={open}
        onClose={() => setTarget(null)}
        title={replacementConfirmTitle(target.name, target.marketValue)}
        className="fa-replacement"
        footer={
          <>
            <Button type="button" variant="ghost" onClick={() => setTarget(null)} data-testid="replacement-confirm-cancel">
              {REPLACEMENT_CANCEL_LABEL}
            </Button>
            <Button
              type="button"
              variant="primary"
              loading={buying}
              disabled={blocked}
              onClick={() => void confirmPurchase()}
              data-testid="replacement-confirm"
            >
              {REPLACEMENT_CONFIRM_LABEL}
            </Button>
          </>
        }
      >
        <dl className="fa-replacement__bill" data-testid="replacement-bill">
          {replacementCreditRows(status.balance, target.name, target.marketValue).map((row) => (
            <div key={row.label} className={row.total ? "fa-replacement__bill-row fa-replacement__bill-row--total" : "fa-replacement__bill-row"}>
              <dt>{row.label}</dt>
              <dd>{row.value}</dd>
            </div>
          ))}
        </dl>
        <p className="fa-field__hint" data-testid="replacement-confirm-note">
          {replacementConfirmNote(status, activeRole)}
        </p>
      </Modal>
    );
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={REPLACEMENT_SHEET_TITLE}
      className="fa-replacement"
      closeLabel={REPLACEMENT_LATER_LABEL}
      footer={
        <div className="fa-replacement__later">
          <Button type="button" variant="ghost" onClick={onClose} data-testid="replacement-later">
            {REPLACEMENT_LATER_LABEL}
          </Button>
          <span className="fa-field__hint">{REPLACEMENT_LATER_NOTE}</span>
        </div>
      }
    >
      <div className="fa-replacement__head" data-testid="replacement-sheet">
        {done ? (
          <p className="fa-replacement__done" data-testid="replacement-done">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M20 6 9 17l-5-5" />
            </svg>
            {done}
          </p>
        ) : null}
        <p data-testid="replacement-intro">{replacementIntro(status.missingRoles)}</p>
        {activeRole ? (
          <ul className="fa-replacement__chips" data-testid="replacement-chips">
            {replacementChips(status, activeRole).map((chip) => (
              <li key={chip} className="fa-replacement__chip">
                {chip}
              </li>
            ))}
          </ul>
        ) : null}
        {status.blockedMessage ? (
          <UiStatePanel state="error" title="Rose ferme" message={status.blockedMessage} testId="replacement-blocked" />
        ) : null}
        {roles.length > 1 ? (
          <div className="fa-replacement__roles" role="radiogroup" aria-label="Ruolo da scegliere">
            {roles.map((item) => (
              <Button
                key={item}
                type="button"
                size="sm"
                variant={item === activeRole ? "primary" : "secondary"}
                aria-pressed={item === activeRole}
                onClick={() => setRole(item)}
                data-testid={`replacement-role-${item}`}
              >
                {roleSingularLabel(item)}
              </Button>
            ))}
          </div>
        ) : null}
        <div className="fa-replacement__filters">
          <Input
            label="Cerca"
            name="replacement-search"
            type="search"
            placeholder={REPLACEMENT_SEARCH_PLACEHOLDER}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            data-testid="replacement-search"
          />
          <Select
            label="Ordina per"
            name="replacement-order"
            options={REPLACEMENT_ORDER_OPTIONS.map((option) => ({ value: option.value, label: option.label }))}
            value={order}
            onChange={(event) => setOrder(event.target.value as TradeReplacementOrder)}
            data-testid="replacement-order"
          />
        </div>
      </div>
      {error ? <UiStatePanel state="error" title="Non è andata" message={error} testId="replacement-error" /> : null}
      {loading && candidates.length === 0 ? (
        <UiStatePanel state="loading" title="Caricamento" message="Cerco i calciatori liberi…" testId="replacement-loading" />
      ) : null}
      {!loading && candidates.length === 0 && !error ? (
        <p className="fa-field__hint" data-testid="replacement-empty">
          {REPLACEMENT_EMPTY_LIST}
        </p>
      ) : null}
      <ul className="fa-replacement__list" data-testid="replacement-list">
        {candidates.map((candidate) => (
          <li
            key={candidate.athleteId}
            className={candidate.affordable ? "fa-replacement__row" : "fa-replacement__row fa-replacement__row--disabled"}
            data-testid={`replacement-candidate-${candidate.athleteId}`}
          >
            <div className="fa-replacement__who">
              <span className="fa-replacement__name">
                {candidate.role} · {candidate.name}
              </span>
              <span className="fa-replacement__meta">
                {candidate.clubName ? <span>{candidate.clubName}</span> : null}
                <MarketValueBadge value={candidate.marketValue} />
                <SeasonAverageBadge average={candidate.seasonAverage} />
              </span>
              {!candidate.affordable ? (
                <span className="fa-replacement__expensive">{REPLACEMENT_TOO_EXPENSIVE}</span>
              ) : null}
            </div>
            <Button
              type="button"
              size="sm"
              variant="primary"
              disabled={!candidate.affordable || blocked}
              onClick={() => {
                setError(null);
                setTarget(candidate);
              }}
              data-testid={`replacement-take-${candidate.athleteId}`}
            >
              {replacementTakeLabel(candidate.marketValue)}
            </Button>
          </li>
        ))}
      </ul>
    </Modal>
  );
}
