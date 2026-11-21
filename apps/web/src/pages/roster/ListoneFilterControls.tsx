import {
  LISTONE_FILTER_ALL_LABEL,
  LISTONE_FILTER_LABEL,
  LISTONE_RESET_FILTERS_LABEL,
  NO_LISTONE_PLACE_FILTERS,
  listoneClubOptions,
  listoneCompetitionOptions,
  listoneFilterChips,
  listoneFilterVisibility,
  listoneOptionLabel,
  removeListoneFilter,
  selectListoneClub,
  selectListoneCompetition,
} from "@fantappero/contracts";
import type { LeagueListoneEntry, ListonePlaceFilters } from "@fantappero/contracts";
import { Select } from "@fantappero/ui";
import { useMemo } from "react";

/**
 * «Campionato» e «Squadra» sotto la ricerca del listone (Rosario, 21/11): due menu nativi
 * affiancati, poi i filtri attivi da togliere uno per uno e «Azzera filtri». Con un
 * campionato solo resta solo «Squadra». La logica è in `@fantappero/contracts`, uguale
 * nell'app.
 */
export function ListoneFilterControls({
  listone,
  place,
  onChange,
}: {
  listone: readonly LeagueListoneEntry[];
  place: ListonePlaceFilters;
  onChange: (place: ListonePlaceFilters) => void;
}) {
  const visibility = useMemo(() => listoneFilterVisibility(listone), [listone]);
  const competitionOptions = useMemo(() => listoneCompetitionOptions(listone), [listone]);
  const clubOptions = useMemo(
    () => listoneClubOptions(listone, place.competitionId),
    [listone, place.competitionId],
  );
  const chips = listoneFilterChips(listone, place);

  if (!visibility.competition && !visibility.club) {
    return null;
  }

  return (
    <div className="fa-listone-filters" data-testid="roster-listone-filters">
      <div
        className={
          visibility.competition
            ? "fa-listone-filters__selects"
            : "fa-listone-filters__selects fa-listone-filters__selects--single"
        }
      >
        {visibility.competition ? (
          <Select
            label={LISTONE_FILTER_LABEL.competition}
            name="roster-listone-competition"
            value={place.competitionId ?? ""}
            onChange={(event) =>
              onChange(selectListoneCompetition(listone, place, event.target.value || null))
            }
            options={[
              { value: "", label: LISTONE_FILTER_ALL_LABEL.competition },
              ...competitionOptions.map((option) => ({ value: option.id, label: option.name })),
            ]}
            data-testid="roster-listone-competition"
          />
        ) : null}
        {visibility.club ? (
          <Select
            label={LISTONE_FILTER_LABEL.club}
            name="roster-listone-club"
            value={place.clubId ?? ""}
            onChange={(event) => onChange(selectListoneClub(listone, place, event.target.value || null))}
            options={[
              { value: "", label: LISTONE_FILTER_ALL_LABEL.club },
              ...clubOptions.map((option) => ({ value: option.id, label: listoneOptionLabel(option) })),
            ]}
            data-testid="roster-listone-club"
          />
        ) : null}
      </div>
      {chips.length > 0 ? (
        <div className="fa-listone-filters__active" role="group" aria-label="Filtri attivi">
          {chips.map((chip) => (
            <button
              key={chip.kind}
              type="button"
              className="fa-listone-filters__chip"
              aria-label={chip.removeLabel}
              onClick={() => onChange(removeListoneFilter(place, chip.kind))}
              data-testid={`roster-listone-chip-${chip.kind}`}
            >
              <span className="fa-listone-filters__chip-pill">
                {chip.label}
                <span aria-hidden="true"> ×</span>
              </span>
            </button>
          ))}
          <button
            type="button"
            className="fa-listone-filters__reset"
            onClick={() => onChange(NO_LISTONE_PLACE_FILTERS)}
            data-testid="roster-listone-reset-filters"
          >
            {LISTONE_RESET_FILTERS_LABEL}
          </button>
        </div>
      ) : null}
    </div>
  );
}
