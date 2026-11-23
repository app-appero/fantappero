/**
 * Conferma di «Salva regolamento» in Amministrazione lega.
 *
 * Dopo il salvataggio la schermata passava da sola alla scheda «Invitati»: il regolamento
 * spariva, a parità di scorrimento si vedeva l'elenco dei fantallenatori e la conferma
 * «Regolamento salvato» (che sta nella scheda Configurazione) non si vedeva (corsa M4, 22/11).
 * Ora si resta sul regolamento con la conferma sopra il pulsante; al primo salvataggio la
 * conferma dice dove si invitano i fantallenatori, come faceva il passaggio automatico.
 *
 * Solo logica pura: gira nei test `node:test`.
 */
export function rulesSavedMessage(firstSave: boolean): string {
  return firstSave
    ? "Le modifiche sono state applicate. Ora puoi invitare i fantallenatori dalla scheda «Invitati»."
    : "Le modifiche sono state applicate.";
}
