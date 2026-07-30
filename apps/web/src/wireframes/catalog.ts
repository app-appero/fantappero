import type { UiState } from "@fantappero/ui";

export const WIREFRAME_STATES = [
  "loading",
  "empty",
  "error",
  "success",
  "forbidden",
] as const satisfies readonly UiState[];

export type Macroflow = "M1" | "M2" | "M3" | "M4";

export type WireframeScreenId =
  | "auth"
  | "league-dashboard"
  | "league-config"
  | "roster"
  | "formation"
  | "matchday"
  | "standings"
  | "auction"
  | "market"
  | "operator-panel";

export type WireframeScreenMeta = {
  id: WireframeScreenId;
  title: string;
  route: string;
  macroflows: readonly Macroflow[];
  primaryCta: string;
  priorityInfo: readonly string[];
  criticalSteps: readonly string[];
  roles: readonly string[];
  openDecisions?: readonly string[];
  empty: { title: string; description: string; ctaLabel?: string };
  error: { title: string; message: string; retryLabel?: string };
  loading: { title: string; message: string };
  forbidden: { title: string; message: string };
};

export const WIREFRAME_CATALOG: readonly WireframeScreenMeta[] = [
  {
    id: "auth",
    title: "Autenticazione",
    route: "/accedi",
    macroflows: ["M1"],
    primaryCta: "Accedi",
    priorityInfo: ["Email", "Password", "Link recupero password"],
    criticalSteps: ["Inserimento credenziali", "Invio form", "Redirect a /leghe"],
    roles: ["Visitatore non autenticato"],
    openDecisions: ["Flusso verifica email (EP02-01)", "Redirect post-login"],
    empty: {
      title: "Nessun account trovato",
      description: "Registrati per creare un account e accedere alle leghe.",
      ctaLabel: "Registrati",
    },
    error: {
      title: "Accesso non riuscito",
      message: "Credenziali non valide o servizio temporaneamente non disponibile.",
      retryLabel: "Riprova",
    },
    loading: {
      title: "Verifica credenziali",
      message: "Autenticazione in corso…",
    },
    forbidden: {
      title: "Sessione non valida",
      message: "Non hai i permessi per accedere a questa area.",
    },
  },
  {
    id: "league-dashboard",
    title: "Dashboard lega",
    route: "/leghe",
    macroflows: ["M1"],
    primaryCta: "Entra in lega",
    priorityInfo: ["Elenco leghe", "Stato lega", "Ruolo utente"],
    criticalSteps: ["Selezione lega attiva", "Accesso al contesto lega"],
    roles: ["Partecipante", "Amministratore di lega"],
    empty: {
      title: "Nessuna lega",
      description: "Crea o unisciti a una lega privata per iniziare la stagione.",
      ctaLabel: "Crea lega",
    },
    error: {
      title: "Leghe non disponibili",
      message: "Impossibile caricare le leghe. Riprova tra poco.",
      retryLabel: "Ricarica",
    },
    loading: {
      title: "Caricamento leghe",
      message: "Recupero delle leghe a cui partecipi…",
    },
    forbidden: {
      title: "Permessi insufficienti",
      message: "Non hai accesso alle leghe di questa area.",
    },
  },
  {
    id: "league-config",
    title: "Configurazione lega",
    route: "/lega/amministrazione",
    macroflows: ["M1"],
    primaryCta: "Salva configurazione",
    priorityInfo: ["Partecipanti", "Regole roster", "Crediti", "Stato lega"],
    criticalSteps: ["Invito membri", "Validazione regole", "Avvio asta/stagione"],
    roles: ["Amministratore di lega"],
    openDecisions: ["Preset regole aggiuntivi oltre Standard"],
    empty: {
      title: "Lega in bozza",
      description: "Aggiungi partecipanti e conferma le regole prima di avviare l'asta.",
      ctaLabel: "Invita partecipanti",
    },
    error: {
      title: "Configurazione non salvata",
      message: "Si è verificato un errore durante il salvataggio.",
      retryLabel: "Riprova",
    },
    loading: {
      title: "Caricamento configurazione",
      message: "Recupero regole e partecipanti…",
    },
    forbidden: {
      title: "Permessi insufficienti",
      message: "Solo l'amministratore di lega può modificare la configurazione.",
    },
  },
  {
    id: "roster",
    title: "Rosa",
    route: "/rosa",
    macroflows: ["M2"],
    primaryCta: "Gestisci rosa",
    priorityInfo: ["Giocatori per ruolo", "Crediti residui", "Stato giocatore"],
    criticalSteps: ["Consultazione listone", "Verifica vincoli roster"],
    roles: ["Partecipante", "Amministratore di lega (gestione)"],
    empty: {
      title: "Rosa vuota",
      description: "Completa l'asta o importa i giocatori per popolare la rosa.",
      ctaLabel: "Vai all'asta",
    },
    error: {
      title: "Rosa non disponibile",
      message: "Impossibile caricare i giocatori della rosa.",
      retryLabel: "Ricarica",
    },
    loading: {
      title: "Caricamento rosa",
      message: "Recupero giocatori e crediti…",
    },
    forbidden: {
      title: "Permessi insufficienti",
      message: "Non puoi visualizzare la rosa di questa lega.",
    },
  },
  {
    id: "formation",
    title: "Formazione",
    route: "/formazione",
    macroflows: ["M2"],
    primaryCta: "Salva formazione",
    priorityInfo: ["Modulo", "Titolari", "Panchina", "Lock progressivo"],
    criticalSteps: ["Scelta modulo", "Assegnazione titolari", "Ordine panchina"],
    roles: ["Partecipante"],
    openDecisions: ["Route dedicata vs tab su /rosa (TBD)"],
    empty: {
      title: "Formazione non impostata",
      description: "Seleziona un modulo e assegna i titolari per il prossimo turno.",
      ctaLabel: "Imposta formazione",
    },
    error: {
      title: "Formazione non salvata",
      message: "Errore durante il salvataggio della formazione.",
      retryLabel: "Riprova",
    },
    loading: {
      title: "Caricamento formazione",
      message: "Recupero modulo e slot disponibili…",
    },
    forbidden: {
      title: "Permessi insufficienti",
      message: "Non puoi modificare la formazione di questa squadra.",
    },
  },
  {
    id: "matchday",
    title: "Turno e risultati",
    route: "/turni",
    macroflows: ["M2", "M3"],
    primaryCta: "Consulta turno",
    priorityInfo: ["Turno corrente", "Partite programmate", "Risultati fantasy"],
    criticalSteps: ["Selezione turno", "Consultazione risultati", "Verifica punteggi"],
    roles: ["Partecipante"],
    empty: {
      title: "Nessun turno attivo",
      description: "La stagione non è ancora iniziata o il calendario è in preparazione.",
      ctaLabel: "Torna alla dashboard",
    },
    error: {
      title: "Turno non disponibile",
      message: "Impossibile caricare calendario e risultati.",
      retryLabel: "Ricarica",
    },
    loading: {
      title: "Caricamento turno",
      message: "Recupero calendario e risultati…",
    },
    forbidden: {
      title: "Permessi insufficienti",
      message: "Non hai accesso ai turni di questa lega.",
    },
  },
  {
    id: "standings",
    title: "Classifica",
    route: "/classifica",
    macroflows: ["M3"],
    primaryCta: "Consulta classifica",
    priorityInfo: ["Posizione", "Punti", "GF/GA", "Criteri spareggio"],
    criticalSteps: ["Visualizzazione ranking", "Identificazione propria squadra"],
    roles: ["Partecipante"],
    empty: {
      title: "Classifica non disponibile",
      description: "La classifica sarà visibile dopo il primo turno disputato.",
      ctaLabel: "Vai ai turni",
    },
    error: {
      title: "Classifica non caricata",
      message: "Errore nel recupero della classifica.",
      retryLabel: "Ricarica",
    },
    loading: {
      title: "Caricamento classifica",
      message: "Calcolo posizioni in corso…",
    },
    forbidden: {
      title: "Permessi insufficienti",
      message: "Non hai accesso alla classifica di questa lega.",
    },
  },
  {
    id: "auction",
    title: "Asta",
    route: "/asta",
    macroflows: ["M3"],
    primaryCta: "Invia offerta",
    priorityInfo: ["Budget residuo", "Giocatore target", "Stato sessione asta"],
    criticalSteps: ["Selezione giocatore", "Inserimento offerta", "Conferma busta"],
    roles: ["Partecipante", "Amministratore di lega (gestione sessione)"],
    openDecisions: ["Asta live in Fase 2 — MVP solo buste chiuse"],
    empty: {
      title: "Asta non avviata",
      description: "L'amministratore deve aprire la sessione d'asta.",
      ctaLabel: "Contatta admin",
    },
    error: {
      title: "Offerta non inviata",
      message: "Errore durante l'invio dell'offerta.",
      retryLabel: "Riprova",
    },
    loading: {
      title: "Caricamento asta",
      message: "Recupero sessione e budget…",
    },
    forbidden: {
      title: "Permessi insufficienti",
      message: "Non puoi partecipare all'asta di questa lega.",
    },
  },
  {
    id: "market",
    title: "Mercato",
    route: "/mercato",
    macroflows: ["M3"],
    primaryCta: "Proponi scambio",
    priorityInfo: ["Svincolati", "Crediti", "Proposte in sospeso"],
    criticalSteps: ["Consultazione svincolati", "Proposta scambio", "Approvazione admin"],
    roles: ["Partecipante", "Amministratore di lega (approvazione)"],
    empty: {
      title: "Mercato chiuso",
      description: "Il mercato aprirà al termine dell'asta o su decisione dell'admin.",
      ctaLabel: "Torna alla dashboard",
    },
    error: {
      title: "Mercato non disponibile",
      message: "Impossibile caricare le operazioni di mercato.",
      retryLabel: "Ricarica",
    },
    loading: {
      title: "Caricamento mercato",
      message: "Recupero svincolati e proposte…",
    },
    forbidden: {
      title: "Permessi insufficienti",
      message: "Non hai accesso al mercato di questa lega.",
    },
  },
  {
    id: "operator-panel",
    title: "Pannello operatore",
    route: "/admin",
    macroflows: ["M1", "M4"],
    primaryCta: "Intervento operatore",
    priorityInfo: ["Anomalie dati", "Leghe globali", "Utenti piattaforma"],
    criticalSteps: ["Monitoraggio anomalie", "Azione auditata", "Verifica esito"],
    roles: ["Operatore globale"],
    openDecisions: ["Dettaglio job EP11-04 non ancora definito"],
    empty: {
      title: "Nessun dato operatore",
      description: "Non ci sono leghe o utenti da visualizzare in questo momento.",
      ctaLabel: "Aggiorna",
    },
    error: {
      title: "Pannello non disponibile",
      message: "Errore nel caricamento dei dati operativi.",
      retryLabel: "Ricarica",
    },
    loading: {
      title: "Caricamento pannello",
      message: "Recupero dati piattaforma…",
    },
    forbidden: {
      title: "Permessi insufficienti",
      message: "Solo gli operatori globali possono accedere a questa area.",
    },
  },
] as const;

export function getWireframeScreen(id: WireframeScreenId): WireframeScreenMeta {
  const screen = WIREFRAME_CATALOG.find((entry) => entry.id === id);
  if (!screen) {
    throw new Error(`Unknown wireframe screen: ${id}`);
  }
  return screen;
}

export const ALL_MACROFLOWS: readonly Macroflow[] = ["M1", "M2", "M3", "M4"];

export function macroflowsCovered(): Set<Macroflow> {
  const covered = new Set<Macroflow>();
  for (const screen of WIREFRAME_CATALOG) {
    for (const flow of screen.macroflows) {
      covered.add(flow);
    }
  }
  return covered;
}
