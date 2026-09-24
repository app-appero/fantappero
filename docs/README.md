# Indice della documentazione — FantApperò

**Versione:** 0.1
**Data:** 24 settembre 2026
**Corrisponde a:** Blocco A2 del piano `FantAppero_Piano_Chiusura_Fase_1.md`.

## Cosa fa questo documento (e cosa non fa)

Questo indice **non elimina né sostituisce nessun documento**. Tutte le fonti elencate sotto restano nel repository e mantengono il loro valore storico e di contesto. Serve a rispondere a una sola domanda, e solo quando si presenta davvero: **se due documenti descrivono in modo diverso la stessa regola puntuale, quale versione è operativa per chi implementa o verifica oggi?**

La gerarchia sotto è un criterio di **tie-break locale**, da applicare voce per voce solo in presenza di una contraddizione reale — non un giudizio generale su quale documento sia "migliore". Un documento a priorità più bassa (es. il Concept iniziale) resta pienamente valido su tutto ciò che non è stato esplicitamente superato da una decisione successiva.

Quando un punto viene effettivamente superato, va marcato `SUPERSEDED` nel registro dei requisiti (`docs/operations/registro_requisiti_fase1.md`), indicando quale documento/decisione più recente prevale — il documento originale non viene toccato.

## Ordine di precedenza in caso di contraddizione puntuale

1. **`docs/operations/`** — decisioni operative correnti: processo pilot, sicurezza, deployment, backup/DR, supporto. Vince su tutto il resto per queste materie perché riflette lo stato operativo più aggiornato e verificato.
2. **`docs/doc_fantapperò/FantAppero_Documento_Master_v0.1.docx`, `FantAppero_Requisiti_Funzionali_MVP_v0.1.docx`, `FantAppero_Architettura_Tecnica_Modello_Dati_MVP_v0.1.docx`** — per il perimetro MVP e il modello dati/architettura approvati.
3. **`docs/adr/`** (Architecture Decision Records) e **`docs/api/`** — per decisioni tecniche e contratti API puntuali.
4. **`📘 Documento di Concept — Progetto Fantacalcio "FantApperò".pdf`** — fonte iniziale e visione di prodotto. Resta valido ovunque non sia stato esplicitamente superato da una decisione successiva approvata.
5. **`docs/design/wireframes.md`** e le altre risorse di design — rappresentazione UI, mai fonte di regole di dominio (es. calcolo punteggi, vincoli di rosa).

## Mappa delle cartelle

| Cartella | Contenuto |
|---|---|
| `docs/operations/` | Processo Beta/pilot, sicurezza, backup/DR, supporto, osservabilità, qualità dati sportivi. Include `beta_readiness/` (pacchetto EP12), `evidence/` (evidenze raccolte), `templates/`, e il registro requisiti (`registro_requisiti_fase1.md`). |
| `docs/doc_fantapperò/` | Documenti fondativi (Concept, Documento Master, Requisiti Funzionali, Architettura Tecnica) e i pacchetti Trello con le card per milestone (M0.5–M5, Pre-M5.1, M5.1/EP13). |
| `docs/adr/` | Architecture Decision Record numerati (ADR-0001…). |
| `docs/api/` | Contratti e comportamento degli endpoint per dominio (auth, leagues, fantasy_turns, ecc.). |
| `docs/data/` | Regole sui dati sportivi: open question API-Football, matrice requisiti, regole di precedenza eventi, copertura dataset. |
| `docs/design/` | Design system, wireframe, linee guida visive — solo rappresentazione, non fonte di regole di dominio. |
| `docs/development/` | Ambiente locale e gate di qualità CI. |
| `docs/FantAppero_Piano_Chiusura_Fase_1.md` | Piano operativo corrente per la chiusura della Fase 1 (questo stesso lavoro). |

## Documenti collegati

- Registro dei requisiti (Blocco A1): [`docs/operations/registro_requisiti_fase1.md`](operations/registro_requisiti_fase1.md)
- Piano di chiusura Fase 1: [`FantAppero_Piano_Chiusura_Fase_1.md`](FantAppero_Piano_Chiusura_Fase_1.md)
