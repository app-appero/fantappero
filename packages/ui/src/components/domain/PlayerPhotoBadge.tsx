import { RoleBadge } from "./RoleBadge.js";

export type PlayerPhotoBadgeProps = {
  photoUrl: string | null | undefined;
  role: string | null | undefined;
  className?: string;
};

/**
 * Foto calciatore con badge ruolo nell'angolo, stesso stile usato in Formazione
 * (`.fa-pitch-player__card`/`__photo`/`__role`). Renderizza `null` quando
 * `photoUrl` è assente: il chiamante resta libero di mostrare il proprio
 * fallback esistente (es. pallino colorato per ruolo) in quel caso.
 */
export function PlayerPhotoBadge({ photoUrl, role, className }: PlayerPhotoBadgeProps) {
  if (!photoUrl) {
    return null;
  }
  return (
    <span className={`fa-pitch-player__card${className ? ` ${className}` : ""}`}>
      <img className="fa-pitch-player__photo" src={photoUrl} alt="" aria-hidden="true" />
      <RoleBadge code={role} className="fa-pitch-player__role" />
    </span>
  );
}
