import { pitchRoleFullLabel, pitchRoleVariant } from "@fantappero/contracts";
import { Badge } from "../Badge.js";

export type RoleBadgeProps = {
  /** Codice ruolo, sia alfabeto provider (G/D/M/F) sia fantacalcio (P/D/C/A). */
  code: string | null | undefined;
  className?: string;
};

/**
 * Badge ruolo unico per tutta l'app: stesso colore/stile per lo stesso ruolo
 * canonico indipendentemente dall'alfabeto d'origine (EP13-P04-quater §1).
 * Mostra il codice originale (non lo traduce) ma con colore coerente, ed
 * espone l'etichetta estesa in tooltip.
 */
export function RoleBadge({ code, className }: RoleBadgeProps) {
  return (
    <Badge
      variant={pitchRoleVariant(code)}
      className={className}
      title={pitchRoleFullLabel(code)}
      data-testid="role-badge"
    >
      {code ?? "?"}
    </Badge>
  );
}
