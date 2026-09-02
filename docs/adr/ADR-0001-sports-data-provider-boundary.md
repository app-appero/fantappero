# ADR-0001 — Confine del provider dati sportivi

| Metadato | Valore |
| --- | --- |
| Stato | Accettato (baseline MVP) |
| Data | 2026-07-27 |
| Decisori | Prodotto + architettura FantApperò (Documento Master v0.1 §15; Architettura tecnica MVP v0.1 §4) |
| Card | EP00-01 |
| Relazioni | Matrice [`../data/api_football_requirement_matrix.md`](../data/api_football_requirement_matrix.md); open questions EP00-02 [`../data/api_football_open_questions.md`](../data/api_football_open_questions.md) |

## Contesto

FantApperò costruisce turni europei, formazioni progressive, fantavoti (Rating Beta + bonus/malus) e uno staff IA consultivo su dati di cinque campionati. API-Football v3 è il **provider principale proposto** per l’MVP.

I documenti di prodotto richiedono:

- sincronizzazione **centrale** (non per utente/client);
- database FantApperò come **fonte di verità applicativa**;
- chiavi API solo sul backend;
- scoring deterministico e auditabile;
- predizioni provider come segnale, non come fatti.

Senza un confine esplicito, i path JSON del provider e le sue ambiguità (assist, autogol, lineup tardive, rating 0–10) propagano assunzioni nel dominio fantasy.

## Decisione

1. **Un solo modulo di integrazione (SPD — Sport Data)** possiede le chiamate ad API-Football, il rate limiting, i retry e la persistenza dei payload grezzi referenziati (object storage / tabella snapshot), non i domini League/Lineup/Scoring/AI.
2. **Anti-corruption layer:** l’adapter traduce risposte esterne in entità normalizzate (`competition`, `club`, `athlete`, `fixture`, `match_event`, `player_match_stat`, `availability`, `transfer`, `official_lineup`, `provider_prediction_snapshot`, …). I moduli fantasy parlano solo di queste entità e di UUID interni.
3. **Gli identificativi e i nomi campo provider non sono parte del modello di dominio fantasy.** Possono comparire solo come attributi tecnici (`provider`, `provider_id`, `provider_event_key`, metadata di snapshot).
4. **Verità di gioco:** kickoff lock, eleggibilità voto, bonus/malus, Rating Beta, sostituzioni e risultati H2H si calcolano su snapshot normalizzati versionati, non su una chiamata live al provider nel request path utente.
5. **Predictions e standings** sono classificati come `signal` per lo staff IA. Non entrano nel motore di scoring né nell’omologazione.
6. **Degradazione:** se il provider è down o incompleto, si serve l’ultimo dato valido con `fetched_at` visibile; non si cancellano entità già acquisite; i gap di convocazione non si risolvono con assunzioni (allineato a FR-RIN-01).
7. **Segreti:** `x-apisports-key` e payload non redatti restano fuori da client, log applicativi di default e repository. La matrice requisiti elenca path di campo, non risposte complete.
8. **Sostituibilità:** un eventuale secondo provider implementa lo stesso contratto di normalizzazione; non si riscrivono FR di gioco contro un vendor.

## Conseguenze

### Positive

- Domini fantasy testabili con fixture congelate (EP00-02 / Architettura §13.3) senza rete.
- Ricalcolo e audit ricostruiscono il fantavoto da input + versione regole.
- Cambio piano API o vendor non impone rename massivi nel frontend.
- Gap di qualità dati restano visibili (matrice §5) invece di nascosti in parsing ad hoc.

### Negative / costi

- Doppio modello (grezzo + normalizzato) e job di sync da operare.
- Latenza di aggiornamento live limitata da quota e polling adattivo.
- Ogni nuovo campo di scoring richiede aggiornamento matrice + test golden, non “lettura diretta” dal JSON vendor.

### Non decisioni (fuori da questo ADR)

- Coefficienti della formula Rating Beta (restano aperti / Beta).
- Regolamento esecutivo su doppia ammonizione.
- Scelta del piano commerciale API-Football.
- Introduzione di `/sidelined`, odds, o provider secondario in parallelo.

## Alternative considerate

| Alternativa | Perché scartata |
| --- | --- |
| Client/app chiama API-Football | Viola FR-DAT-01 / NFR-SEC; quota e chiavi esposte; dati non riusabili tra leghe |
| Domini fantasy dipendono dai DTO vendor | Accoppiamento; impossibile versionare regole su snapshot stabili |
| Usare `games.rating` provider come voto | Contrasta Master §8.3; non spiegabile come Rating FantApperò |
| Trattare `/predictions` come dato ufficiale | Contrasta Master §15 e Architettura §9 |

## Compliance checklist

- [x] Provider mediato dal backend
- [x] DB interno = source of truth applicativa
- [x] Nessuna chiave in documentazione di mapping
- [x] Segnali IA distinti dai fatti di scoring
- [x] Gap bloccanti tracciati per EP00-02 senza inventare mapping di dominio
