import type { FantasyRole, LeagueListoneEntry } from "@fantappero/contracts";
import { PlayerPhotoBadge } from "@fantappero/ui";
import { useEffect, useMemo, useState } from "react";
import { AthleteName } from "../athletes/AthleteCard";

const PAGE_SIZE = 10;
const ROLE_PILLS: Array<{ value: "all" | FantasyRole; label: string }> = [
  { value: "all", label: "Tutti" },
  { value: "P", label: "Portieri" },
  { value: "D", label: "Difensori" },
  { value: "C", label: "Centrocampisti" },
  { value: "A", label: "Attaccanti" },
];

/**
 * Scelta di calciatori dal listone: solo i disponibili (non in rosa a nessuno), con ricerca,
 * filtro per ruolo e pagine da 10. `single` seleziona un solo giocatore; altrimenti l'ordine
 * di selezione diventa il numero accanto al nome.
 */
export function AthleteChooser({
  entries,
  ownedAthleteIds,
  selected,
  onToggle,
  single = false,
  testId,
}: {
  entries: LeagueListoneEntry[];
  ownedAthleteIds: Set<string>;
  selected: string[];
  onToggle: (athleteId: string) => void;
  single?: boolean;
  testId?: string;
}) {
  const [query, setQuery] = useState("");
  const [role, setRole] = useState<"all" | FantasyRole>("all");
  const [page, setPage] = useState(0);

  const available = useMemo(
    () => entries.filter((entry) => !ownedAthleteIds.has(entry.athleteId)),
    [entries, ownedAthleteIds],
  );
  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("it-IT");
    return available.filter(
      (entry) =>
        (role === "all" || entry.effectiveRole === role) &&
        (!needle || `${entry.canonicalName} ${entry.clubName ?? ""}`.toLocaleLowerCase("it-IT").includes(needle)),
    );
  }, [available, query, role]);

  useEffect(() => {
    setPage(0);
  }, [query, role]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const rows = filtered.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE);
  const countFor = (value: "all" | FantasyRole) =>
    value === "all" ? available.length : available.filter((entry) => entry.effectiveRole === value).length;

  return (
    <div className="fa-athlete-chooser" data-testid={testId}>
      <input
        type="search"
        className="fa-athlete-chooser__search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Cerca per nome o squadra"
        aria-label="Cerca calciatore"
      />
      <div className="fa-athlete-chooser__pills" role="tablist">
        {ROLE_PILLS.map((pill) => (
          <button
            key={pill.value}
            type="button"
            role="tab"
            aria-selected={role === pill.value}
            className={role === pill.value ? "fa-athlete-chooser__pill fa-athlete-chooser__pill--active" : "fa-athlete-chooser__pill"}
            onClick={() => setRole(pill.value)}
          >
            {pill.label} {countFor(pill.value)}
          </button>
        ))}
      </div>
      <p className="fa-athlete-chooser__count">
        {filtered.length} {filtered.length === 1 ? "giocatore disponibile" : "giocatori disponibili"}
        {selected.length > 0 && !single ? ` · ${selected.length} scelti` : ""}
      </p>
      {rows.length === 0 ? <p className="fa-athlete-chooser__count">Nessun giocatore disponibile con questi filtri.</p> : null}
      <ul className="fa-athlete-chooser__list">
        {rows.map((entry) => {
          const position = selected.indexOf(entry.athleteId) + 1;
          const active = position > 0;
          return (
            <li key={entry.athleteId}>
              <button
                type="button"
                role={single ? "radio" : "checkbox"}
                aria-checked={active}
                className={active ? "fa-athlete-chooser__row fa-athlete-chooser__row--active" : "fa-athlete-chooser__row"}
                onClick={() => onToggle(entry.athleteId)}
                data-testid={testId ? `${testId}-${entry.athleteId}` : undefined}
              >
                <span className="fa-athlete-chooser__mark">{active ? (single ? "✓" : position) : ""}</span>
                {entry.photoUrl ? (
                  <PlayerPhotoBadge
                    className="fa-athlete-chooser__dot"
                    photoUrl={entry.photoUrl}
                    role={entry.effectiveRole}
                  />
                ) : (
                  <span className={`fa-athlete-chooser__dot fa-athlete-chooser__dot--${entry.effectiveRole}`}>
                    {entry.effectiveRole}
                  </span>
                )}
                <span className="fa-athlete-chooser__name">
                  <AthleteName athleteId={entry.athleteId}>{entry.canonicalName}</AthleteName>
                  {entry.clubName ? <small>{entry.clubName}</small> : null}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      {pageCount > 1 ? (
        <div className="fa-athlete-chooser__pager">
          <button type="button" disabled={safePage === 0} onClick={() => setPage(safePage - 1)}>
            Precedente
          </button>
          <span>
            Pagina {safePage + 1} di {pageCount}
          </span>
          <button type="button" disabled={safePage >= pageCount - 1} onClick={() => setPage(safePage + 1)}>
            Successiva
          </button>
        </div>
      ) : null}
    </div>
  );
}
