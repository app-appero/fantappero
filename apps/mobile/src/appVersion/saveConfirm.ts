/**
 * «Sei sicuro?» prima di salvare la versione dell'app nel pannello operatore → «Versione app»
 * (decisione di Rosario del 23/11): salvare un versionCode nuovo manda la notifica «È
 * disponibile la versione X dell'app» e fa comparire l'avviso nell'app, quindi prima si chiede
 * conferma con `Alert.alert`, come le altre conferme dell'app («Annulla» / «Annuncia»). Testi
 * in comune con il sito (`appVersionSaveConfirmation` di `@fantappero/contracts`).
 *
 * Solo logica pura e import di tipo: gira nei test `node:test`; l'`alert` arriva dalla
 * schermata (`Alert.alert`).
 */
import type { AppVersionSaveConfirmation } from "@fantappero/contracts";

export type ConfirmAlertButton = {
  text: string;
  style?: "default" | "cancel" | "destructive";
  onPress?: () => void;
};

export type ConfirmAlert = (title: string, message: string, buttons: ConfirmAlertButton[]) => void;

/** Mostra la conferma; `onConfirm` parte solo con il tasto di conferma, «Annulla» non fa nulla. */
export function confirmAppVersionSave(
  alert: ConfirmAlert,
  confirmation: AppVersionSaveConfirmation,
  onConfirm: () => void,
): void {
  alert(confirmation.title, confirmation.message, [
    { text: confirmation.cancelLabel, style: "cancel" },
    { text: confirmation.confirmLabel, onPress: onConfirm },
  ]);
}
