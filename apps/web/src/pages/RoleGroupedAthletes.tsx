import { AthleteName } from "../athletes/AthleteCard";

const ROLES: Array<{ role: string; title: string }> = [
  { role: "P", title: "Portieri" },
  { role: "D", title: "Difensori" },
  { role: "C", title: "Centrocampisti" },
  { role: "A", title: "Attaccanti" },
];

export type RoleGroupedRow = {
  athleteId: string;
  name: string;
  role: string | null;
  price: number | null;
};

/** Elenco selezionabile di calciatori diviso per ruolo (Portieri → Attaccanti), come nell'app. */
export function RoleGroupedAthletes({
  rows,
  checked,
  onToggle,
  disabled = false,
}: {
  rows: RoleGroupedRow[];
  checked: string[];
  onToggle: (athleteId: string) => void;
  disabled?: boolean;
}) {
  const groups = [...ROLES, { role: "", title: "Senza ruolo" }]
    .map((group) => ({
      ...group,
      rows: rows.filter((row) => (group.role === "" ? !ROLES.some((r) => r.role === row.role) : row.role === group.role)),
    }))
    .filter((group) => group.rows.length > 0);
  return (
    <div className="fa-trade-roles">
      {groups.map((group) => (
        <section key={group.role || "none"} className="fa-trade-role" data-role={group.role || undefined}>
          <h4 className="fa-trade-role__head">
            <span className="fa-trade-role__dot">{group.role || "?"}</span>
            <span className="fa-trade-role__title">{group.title}</span>
            <span className="fa-trade-role__count">
              {group.rows.filter((row) => checked.includes(row.athleteId)).length}/{group.rows.length}
            </span>
          </h4>
          <div className="fa-trade-athlete-list">
            {group.rows.map((row) => (
              <label key={row.athleteId}>
                <input
                  type="checkbox"
                  checked={checked.includes(row.athleteId)}
                  disabled={disabled}
                  onChange={() => onToggle(row.athleteId)}
                />
                <AthleteName athleteId={row.athleteId}>{row.name}</AthleteName>
                {row.price != null ? <span className="fa-trade-role__price">{row.price}</span> : null}
              </label>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
