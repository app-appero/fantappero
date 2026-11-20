/**
 * Email da mostrare sotto il nome di un fantallenatore (directory e profilo), o `null`.
 *
 * Il backend la manda solo all'admin della lega e all'operatore (per tutti gli altri è
 * `null`): serve a distinguere account diversi con lo stesso nome mostrato. L'app non
 * decide chi la vede: la mostra quando c'è.
 */
export function visibleCoachEmail(coach: { email?: string | null }): string | null {
  const email = coach.email?.trim();
  return email ? email : null;
}

/**
 * Etichetta accessibile della card che apre il profilo: con l'email, quando è visibile,
 * anche chi usa il lettore di schermo distingue due fantallenatori con lo stesso nome.
 */
export function coachProfileAccessibilityLabel(coach: {
  displayName: string;
  email?: string | null;
}): string {
  const email = visibleCoachEmail(coach);
  return email
    ? `Apri il profilo di ${coach.displayName} (${email})`
    : `Apri il profilo di ${coach.displayName}`;
}
