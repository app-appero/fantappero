# Wireframe schermate principali (EPUI-04)

Wireframe responsive navigabili nella web app per validare struttura e gerarchia dei flussi prima dell’implementazione dettagliata. Copy in italiano; componenti presentazionali in `@fantappero/ui`, metadati flusso in `apps/web/src/wireframes/catalog.ts`.

## Inventario schermate

| Schermata | Route | Macroflusso | Ruoli |
| --- | --- | --- | --- |
| Autenticazione | `/accedi` | M1 | Visitatore |
| Dashboard lega | `/leghe` | M1 | Partecipante, Admin lega |
| Configurazione | `/lega/amministrazione` | M1 | Admin lega |
| Rosa | `/rosa` | M2 | Partecipante, Admin lega |
| Formazione | `/formazione` | M2 | Partecipante |
| Turno + Risultati | `/turni` (tab) | M2, M3 | Partecipante |
| Classifica | `/classifica` | M3 | Partecipante |
| Asta | `/asta` | M3 | Partecipante, Admin lega |
| Mercato | `/mercato` | M3 | Partecipante, Admin lega |
| Pannello operatore | `/admin`, `/admin/leghe`, `/admin/utenti` | M1, M4 | Operatore globale |

Turno e risultati condividono la route `/turni` con tab dedicate (decisione documentata sotto).

## Stati UI

Ogni schermata supporta i cinque stati standard via query string:

| Stato | Parametro | Componente |
| --- | --- | --- |
| Caricamento | `?stato=loading` | `UiStatePanel` + `Skeleton` |
| Vuoto | `?stato=empty` | `EmptyState` + CTA primaria |
| Errore | `?stato=error` | `UiStatePanel` + retry |
| Successo | `?stato=success` (default) | Layout wireframe completo |
| Permessi insufficienti | `?stato=forbidden` | `UiStatePanel` inline; oppure gate reale su route protette |

Annotazioni PO (CTA, passaggi critici): aggiungere `?meta=1` oppure aprire `/dev/wireframes`.

## Flussi — CTA e passaggi critici

### M1 — Fondamenta

| Schermata | CTA primaria | Info prioritarie | Passaggi critici |
| --- | --- | --- | --- |
| Autenticazione | Accedi | Email, password, recupero | Credenziali → invio → redirect |
| Dashboard lega | Entra in lega | Elenco leghe, stato, ruolo | Selezione lega attiva |
| Configurazione | Salva configurazione | Partecipanti, regole, crediti | Inviti → validazione → avvio |
| Pannello operatore | Intervento operatore | Anomalie, leghe, utenti | Monitoraggio → azione auditata |

### M2 — Rosa e turni

| Schermata | CTA primaria | Info prioritarie | Passaggi critici |
| --- | --- | --- | --- |
| Rosa | Gestisci rosa | Giocatori, crediti, stato | Listone → vincoli |
| Formazione | Salva formazione | Modulo, titolari, panchina | Modulo → titolari → ordine panchina |
| Turno | Consulta turno | Turno corrente, partite | Selezione turno → calendario |

### M3 — Risultati e mercato

| Schermata | CTA primaria | Info prioritarie | Passaggi critici |
| --- | --- | --- | --- |
| Risultati (tab) | — | Punteggi fantasy, provvisorio/definitivo | Consultazione esito turno |
| Classifica | Consulta classifica | Posizione, punti, GF/GA | Ranking → propria squadra |
| Asta | Invia offerta | Budget, giocatore, sessione | Target → offerta → conferma |
| Mercato | Proponi scambio | Svincolati, crediti, proposte | Svincolati → proposta → approvazione |

### M4 — Operatore piattaforma

Estensione del pannello `/admin/*` con anomalie dati, leghe globali e utenti — azioni sempre auditabili lato server (implementazione EP11-04).

## Matrice ruoli

| Azione | Partecipante | Admin lega | Operatore globale |
| --- | --- | --- | --- |
| Visualizza leghe/turni/classifica | Sì | Sì | Sì (superficie admin) |
| Configura lega / approva mercato | No | Sì | No (salvo intervento piattaforma) |
| Gestisce sessione asta | No | Sì | No |
| Pannello `/admin/*` | No | No | Sì |

Demo permessi web: `?persona=admin` (admin lega), `?persona=operator` (operatore globale).

## Decisioni non approvate (TBD)

Queste voci sono **segnalate nei wireframe** con badge TBD e **non** implementate come regole:

- Autenticazione reale e redirect post-login (EP02-01)
- Verifica email e reset password (EP02-01)
- Asta live — MVP solo buste chiuse; live in Fase 2
- Formazione: route dedicata `/formazione` vs tab su `/rosa` (attualmente route dedicata)
- Turno/risultati: tab su `/turni` vs route separate (attualmente tab)
- Preset regole oltre Standard in configurazione lega
- Dettaglio job operatore (EP11-04)

## Verifica locale

Hub dev: [`/dev/wireframes`](http://localhost:5173/dev/wireframes)

| Scenario | URL demo |
| --- | --- |
| Auth successo | `/accedi?stato=success&meta=1` |
| Leghe vuote | `/leghe?stato=empty` |
| Classifica loading | `/classifica?stato=loading` |
| Asta admin | `/asta?persona=admin&stato=success` |
| Mercato forbidden | `/mercato?stato=forbidden` |
| Operatore | `/admin?persona=operator&stato=success` |

```powershell
pnpm typecheck
pnpm lint
pnpm test:packages
pnpm test:web
pnpm build:web
```

**Mobile RN:** wireframe completi solo su web responsive; l’app mobile mantiene shell tab bar allineata alle etichette nav.

## Riferimenti codice

- Catalogo: `apps/web/src/wireframes/catalog.ts`
- Pagine: `apps/web/src/wireframes/screens/*`
- Componenti UI: `StandingsTable`, `AuctionBidPanel`, `AuthFormLayout`, `WireframeSection` in `@fantappero/ui`
- Route: `apps/web/src/routes.tsx`
