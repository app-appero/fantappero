import type { AthleteCard } from "@fantappero/contracts";
import { formatFantasyPoints } from "@fantappero/contracts";
import { Modal, UiStatePanel } from "@fantappero/ui";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type MouseEvent,
  type ReactNode,
} from "react";
import { fetchAthleteCard } from "../api/leagues";
import { getApiErrorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";

const ROLE_LABEL: Record<string, string> = {
  P: "Portiere",
  D: "Difensore",
  C: "Centrocampista",
  A: "Attaccante",
};

type AthleteCardContextValue = {
  open: (athleteId: string) => void;
};

const AthleteCardContext = createContext<AthleteCardContextValue | null>(null);

export function useAthleteCard(): AthleteCardContextValue | null {
  return useContext(AthleteCardContext);
}

/** Nome cliccabile. Senza provider resta testo, così i test di pagina non cambiano. */
export function AthleteName({
  athleteId,
  children,
  className,
}: {
  athleteId?: string | null;
  children: ReactNode;
  className?: string;
}) {
  const card = useAthleteCard();
  if (!card || !athleteId) {
    return <span className={className}>{children}</span>;
  }
  return (
    <button
      type="button"
      className={className ? `fa-athlete-name ${className}` : "fa-athlete-name"}
      onClick={(event: MouseEvent<HTMLButtonElement>) => {
        event.preventDefault();
        event.stopPropagation();
        card.open(athleteId);
      }}
    >
      {children}
    </button>
  );
}

function formatIsoDate(value: string | null): string | null {
  if (!value) {
    return null;
  }
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) {
    return value;
  }
  return `${match[3]}/${match[2]}/${match[1]}`;
}

function roleLabel(code: string | null): string | null {
  if (!code) {
    return null;
  }
  return ROLE_LABEL[code] ? `${ROLE_LABEL[code]} (${code})` : code;
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) {
    return "?";
  }
  if (parts.length === 1) {
    return parts[0]!.slice(0, 2).toUpperCase();
  }
  return `${parts[0]!.charAt(0)}${parts[parts.length - 1]!.charAt(0)}`.toUpperCase();
}

export function AthleteCardView({ card }: { card: AthleteCard }) {
  const facts: Array<{ label: string; value: string }> = [];
  const birth = formatIsoDate(card.birthDate);
  if (birth) {
    facts.push({ label: "Nascita", value: card.age != null ? `${birth} · ${card.age} anni` : birth });
  } else if (card.age != null) {
    facts.push({ label: "Età", value: `${card.age} anni` });
  }
  if (card.nationality) {
    facts.push({ label: "Nazionalità", value: card.nationality });
  }
  if (card.height) {
    facts.push({ label: "Altezza", value: card.height });
  }
  if (card.weight) {
    facts.push({ label: "Peso", value: card.weight });
  }
  const role = roleLabel(card.effectiveRole ?? card.role);
  if (role) {
    facts.push({
      label: card.effectiveRole && card.role && card.effectiveRole !== card.role ? "Ruolo in lega" : "Ruolo",
      value: role,
    });
  }
  if (card.providerPositionRaw) {
    facts.push({ label: "Posizione provider", value: card.providerPositionRaw });
  }
  if (card.shirtNumber != null) {
    facts.push({ label: "Maglia", value: String(card.shirtNumber) });
  }
  if (card.injured != null) {
    facts.push({ label: "Stato", value: card.injured ? "Infortunato" : "Disponibile" });
  }
  if (card.live) {
    facts.unshift({
      label: "Voto live",
      value: card.live.score != null ? `${formatFantasyPoints(card.live.score)}${card.live.isFantasy ? "" : " (voto provider)"}` : "In corso",
    });
  }
  if (card.seasonStats) {
    const st = card.seasonStats;
    facts.push(
      { label: "Media voto", value: st.averageRating != null ? formatFantasyPoints(st.averageRating) : "—" },
      { label: "Media fantacalcio", value: st.fantasyAverage != null ? formatFantasyPoints(st.fantasyAverage) : "—" },
      { label: "Partite giocate", value: String(st.matches) },
      { label: "Gol", value: String(st.goals) },
      { label: "Assist", value: String(st.assists) },
    );
  }

  return (
    <div className="fa-athlete-card" data-testid="athlete-card">
      <div className="fa-athlete-card__hero">
        {card.photoUrl ? (
          <img className="fa-athlete-card__photo" src={card.photoUrl} alt="" />
        ) : (
          <div className="fa-athlete-card__photo fa-athlete-card__photo--empty" aria-hidden="true">
            {initials(card.canonicalName)}
          </div>
        )}
        <div>
          <p className="fa-athlete-card__club">
            {[card.firstName, card.lastName].filter(Boolean).join(" ") || card.canonicalName}
          </p>
          <p className="fa-athlete-card__club">{card.clubName ?? "Club non disponibile"}</p>
        </div>
      </div>
      <dl className="fa-athlete-card__facts">
        {facts.map((fact) => (
          <div key={fact.label} className="fa-athlete-card__fact">
            <dt>{fact.label}</dt>
            <dd>{fact.value}</dd>
          </div>
        ))}
      </dl>
      <section className="fa-athlete-card__section">
        <h3>Stagioni</h3>
        {card.seasons.length === 0 ? (
          <p className="fa-athlete-card__muted">Nessuna stagione salvata dal provider.</p>
        ) : (
          <ul className="fa-athlete-card__list">
            {card.seasons.map((season) => (
              <li key={`${season.seasonYear}-${season.clubName}-${season.shirtNumber ?? ""}`}>
                {season.seasonYear} · {season.clubName}
                {season.shirtNumber != null ? ` · n. ${season.shirtNumber}` : ""}
                {season.positionRaw ? ` · ${season.positionRaw}` : ""}
                {season.isActive ? " · in rosa" : ""}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

export function AthleteCardProvider({ children }: { children: ReactNode }) {
  const { activeLeagueId, isDemoMode } = useAuth();
  const [athleteId, setAthleteId] = useState<string | null>(null);
  const [card, setCard] = useState<AthleteCard | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const open = useCallback((nextId: string) => {
    setAthleteId(nextId);
  }, []);

  const close = useCallback(() => {
    setAthleteId(null);
  }, []);

  useEffect(() => {
    if (!athleteId) {
      setCard(null);
      setError(null);
      setLoading(false);
      return;
    }
    if (isDemoMode) {
      setCard(null);
      setLoading(false);
      setError("La scheda completa è disponibile in una lega reale.");
      return;
    }
    if (!activeLeagueId) {
      setCard(null);
      setLoading(false);
      setError("Seleziona una lega per aprire la scheda del calciatore.");
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setCard(null);
      setLoading(false);
      setError("Accedi per aprire la scheda del calciatore.");
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setCard(null);
    fetchAthleteCard(stored.accessToken, activeLeagueId, athleteId)
      .then((result) => {
        if (!cancelled) {
          setCard(result);
        }
      })
      .catch((loadError: unknown) => {
        if (!cancelled) {
          setError(getApiErrorMessage(loadError, "Impossibile caricare la scheda."));
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
  }, [activeLeagueId, athleteId, isDemoMode]);

  return (
    <AthleteCardContext.Provider value={{ open }}>
      {children}
      <Modal
        open={athleteId != null}
        onClose={close}
        title={card?.canonicalName ?? "Calciatore"}
        className="fa-athlete-card-dialog"
      >
        {loading ? (
          <UiStatePanel
            state="loading"
            title="Caricamento scheda"
            message="Recupero foto, anagrafica e rosa di lega…"
            testId="athlete-card-loading"
          />
        ) : null}
        {!loading && error ? (
          <UiStatePanel
            state="error"
            title="Scheda non disponibile"
            message={error}
            testId="athlete-card-error"
          />
        ) : null}
        {!loading && !error && card ? <AthleteCardView card={card} /> : null}
      </Modal>
    </AthleteCardContext.Provider>
  );
}
