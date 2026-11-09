/**
 * Informativa privacy del pilota — fonte unica per web e app.
 * Allinea sempre `docs/operations/pilot_privacy_notice.md` e, quando il testo cambia,
 * incrementa `PROFILE_POLICY_VERSION` (backend) così a tutti viene richiesto un nuovo consenso.
 */
export const PRIVACY_NOTICE_VERSION = "2026-11b";
export const PRIVACY_CONTACT_EMAIL = "info@fantappero.it";

export type PrivacyNoticeSection = {
  id: string;
  title: string;
  paragraphs?: readonly string[];
  bullets?: readonly string[];
};

export const PRIVACY_NOTICE_TITLE = "Informativa privacy — pilota";

export const PRIVACY_NOTICE_INTRO =
  "FantApperò è un'applicazione di fantacalcio in fase di test (pilota). Usandola accetti che " +
  "il progetto è ancora in sviluppo: possono esserci bug, interruzioni o, in casi eccezionali, " +
  "perdita di dati non recuperabile.";

export const PRIVACY_NOTICE_SECTIONS: readonly PrivacyNoticeSection[] = [
  {
    id: "titolare",
    title: "Chi tratta i dati",
    paragraphs: [
      `Il progetto FantApperò, gestito da Rosario Trotta (${PRIVACY_CONTACT_EMAIL}), che è anche il tuo contatto per qualsiasi richiesta.`,
    ],
  },
  {
    id: "dati",
    title: "Cosa raccogliamo",
    bullets: [
      "Account: l'indirizzo email e il nome del tuo account Google (accedi con Google: non riceviamo né salviamo la tua password Google), il nome o soprannome che scegli di mostrare agli altri partecipanti e l'eventuale foto profilo che carichi.",
      "Dati di gioco: leghe a cui partecipi, rosa, formazioni, risultati, scambi di mercato.",
      "Segnalazioni: se usi «Segnala un problema», il testo che scrivi, le immagini o i video che alleghi, la schermata da cui scrivi e informazioni tecniche (tipo di dispositivo, sistema, versione dell'app). Gli allegati sono visibili solo a chi gestisce il progetto.",
      "Notifiche: se le attivi nell'app Android, un identificativo del dispositivo per inviarti le notifiche e le tue preferenze di notifica.",
    ],
  },
  {
    id: "finalita",
    title: "Perché li raccogliamo",
    paragraphs: [
      "Solo per far funzionare il gioco (crearti l'account, farti entrare nelle leghe, calcolare punteggi e classifiche, avvisarti di eventi di gioco) e per capire e correggere i problemi che ci segnali. Non vendiamo né cediamo i tuoi dati, non facciamo pubblicità né profilazione.",
      "Usiamo fornitori tecnici (hosting dell'app e del database, servizio di posta, servizio di notifiche) che trattano i dati solo per conto del progetto.",
    ],
  },
  {
    id: "conservazione",
    title: "Per quanto tempo",
    paragraphs: [
      "Finché il tuo account esiste. Le segnalazioni si cancellano insieme all'account o su tua richiesta.",
    ],
  },
  {
    id: "diritti",
    title: "I tuoi diritti",
    bullets: [
      `Chiedere una copia di tutti i tuoi dati (comprese le segnalazioni) scrivendo a ${PRIVACY_CONTACT_EMAIL}.`,
      "Cancellare il tuo account: l'email viene sostituita con un valore anonimo, profilo, avatar, segnalazioni e relativi file vengono eliminati, le sessioni chiuse. Il nome che avevi scelto resta solo nelle classifiche storiche delle leghe (così i compagni non perdono la storia della stagione), scollegato dalla tua identità.",
    ],
  },
  {
    id: "contatti",
    title: "Contatti",
    paragraphs: [
      `Per qualsiasi domanda o richiesta scrivi a ${PRIVACY_CONTACT_EMAIL}. Non inviare mai password o codici di accesso: non ne abbiamo bisogno per aiutarti.`,
    ],
  },
  {
    id: "eta",
    title: "Età minima",
    paragraphs: ["Il pilota non è aperto a persone minorenni."],
  },
];
