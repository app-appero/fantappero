# Segnalazioni degli utenti (feedback)

Sezione «Segnala un problema» per web e app: l'utente descrive un bug o un'idea e, se vuole,
allega immagini o video. Le segnalazioni arrivano **solo agli operatori**, che le gestiscono dal
pannello e ricevono una notifica.

## Per l'utente
- Web: voce di menu **Segnala un problema** (`/feedback`). App: stessa voce nel menu.
- Categoria (bug, suggerimento, altro), testo (10–2000 caratteri), fino a **3 allegati**:
  immagini JPEG/PNG/WebP/GIF fino a 8 MB, video MP4/MOV/WebM fino a 50 MB.
- Vede l'elenco delle proprie segnalazioni con lo stato (Ricevuta, In lavorazione, Risolta, Chiusa).
  Non vede note interne né dati di altri utenti.
- Il contesto tecnico (ultima schermata vista, piattaforma, versione, dispositivo) viaggia da solo.

## Per gli operatori
- **Notifica**: in-app e push, solo agli utenti con ruolo operatore (mai all'autore, mai agli altri
  utenti). Nessuna email. Toccandola si apre il pannello Segnalazioni.
- Pannello: web `/admin/feedback`, app → menu operatore → **Segnalazioni**. Filtro per stato,
  conteggio «da leggere», autore, contesto, allegati, nota interna, cambio stato.
- **Impersona**: accanto all'autore c'è il pulsante «Impersona» (con conferma e audit log, come
  nella pagina Utenti). Entra come l'utente direttamente nella pagina o schermata da cui ha
  segnalato il problema. Non compare per se stessi né per utenti eliminati.
- Su web immagini e video si vedono in pagina; sull'app le immagini in anteprima e il video si
  apre nel lettore del telefono (l'app non ha un player integrato).

## API
| Metodo | Percorso | Chi | Note |
| --- | --- | --- | --- |
| `POST` | `/feedback` | utente | `multipart/form-data`: `message`, `category`, `pageContext`, `platform`, `appVersion`, `files[]` |
| `GET` | `/feedback/me` | utente | le proprie segnalazioni |
| `GET` | `/admin/feedback?status=&page=` | operatore | elenco con allegati e `newCount` |
| `PATCH` | `/admin/feedback/{id}` | operatore | `status`, `operatorNote` |
| `GET` | `/feedback/media/{attachmentId}?token=` | link firmato | vedi sotto |

## Sicurezza e privacy
- **Allegati privati**: salvati su disco con nome neutro (`<uuid>.<ext>`), mai con il nome scelto
  dall'utente. Il tipo è riconosciuto **dal contenuto**, non dal nome o dal tipo dichiarato.
- **Lettura**: l'operatore ottiene dal dettaglio link firmati (HMAC con `JWT_SECRET_KEY`), validi per
  **un solo allegato** e **15 minuti**, così funzionano in `<img>`, `<video>` e nel browser del
  telefono. Risposta `private, no-store`, `nosniff`. Un link scaduto va rigenerato con «Aggiorna».
- **Anti-spam**: massimo 10 segnalazioni per utente nell'ultima ora (HTTP 429).
- **Limite del corpo**: il resto dell'API resta a 10 MiB; solo `POST /feedback` ammette fino a 60 MiB.
- **Dati personali**: l'**esportazione dati** dell'utente include le sue segnalazioni; **eliminando
  l'account** si cancellano testo, righe e file allegati.
- Il testo libero e gli allegati possono contenere dati personali: l'informativa del pilota
  (`pilot_privacy_notice.md`) non cita ancora questa raccolta e va aggiornata dal privacy contact.

## Configurazione
| Variabile | Default | Significato |
| --- | --- | --- |
| `FEEDBACK_STORAGE_PATH` | `<AVATAR_STORAGE_PATH>/feedback-private` | cartella privata degli allegati |
| `FEEDBACK_IMAGE_MAX_BYTES` | 8 MiB | peso massimo immagine |
| `FEEDBACK_VIDEO_MAX_BYTES` | 50 MiB | peso massimo video |
| `FEEDBACK_MAX_ATTACHMENTS` | 3 | allegati per segnalazione |
| `FEEDBACK_HOURLY_LIMIT` | 10 | segnalazioni per utente all'ora |
| `FEEDBACK_MEDIA_LINK_TTL_SECONDS` | 900 | durata dei link firmati |

**Persistenza**: il default sta nel volume degli avatar (su Railway `/data/avatars`, già persistente),
quindi gli allegati sopravvivono ai deploy senza un secondo volume. Il mount pubblico
`/media/avatars` serve solo i file nella radice e **non** le sottocartelle, per non esporre gli
allegati. Se imposti `FEEDBACK_STORAGE_PATH` altrove, deve stare su un volume persistente e **non**
sotto una cartella servita come statica.

Migrazione: `b7e2f4a91c30` (tabelle `feedback_reports`, `feedback_attachments`).
Se il proxy davanti all'API limita la dimensione delle richieste, deve ammettere almeno 60 MiB su
`POST /feedback`, altrimenti i video grandi vengono rifiutati prima di arrivare all'app.
