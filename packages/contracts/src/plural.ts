/**
 * Singolare/plurale dei conteggi mostrati all'utente: con 1 niente «1 inviti» o
 * «Mancano 1 titolari» (QA 24-25/11). Solo logica pura, condivisa da sito e app.
 */

/** «1 invito» / «3 inviti»: il numero con la parola accordata. */
export function countWithNoun(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

/** «manca 1» / «mancano 3». */
export function missingCount(count: number): string {
  return count === 1 ? "manca 1" : `mancano ${count}`;
}

/** Etichetta accessibile del badge degli inviti ricevuti: «1 invito in attesa di risposta». */
export function pendingInvitesA11yLabel(count: number): string {
  return `${countWithNoun(count, "invito", "inviti")} in attesa di risposta`;
}

/** Pulsante di salvataggio della formazione incompleta: «Manca 1 titolare» / «Mancano 3 titolari». */
export function missingStartersLabel(count: number): string {
  return count === 1 ? "Manca 1 titolare" : `Mancano ${count} titolari`;
}
