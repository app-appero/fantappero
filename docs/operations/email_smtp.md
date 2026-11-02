# Invio email: Resend e SMTP

L'app invia email (verifica registrazione, inviti, reset password, messaggi degli operatori) con due
trasporti che **convivono**. Resend non è stato rimosso.

| Trasporto | Come funziona | Piani Railway |
| --- | --- | --- |
| **Resend** (API HTTPS) | `RESEND_API_KEY` | tutti i piani |
| **SMTP** | `SMTP_*` | solo **Pro** e superiori; bloccato su Free, Trial e Hobby ([docs Railway](https://docs.railway.com/reference/outbound-networking)) |

## Perché serve l'SMTP
Finché il dominio non è verificato su Resend, Resend invia **solo all'indirizzo del titolare
dell'account** (HTTP 403 verso gli altri): nessun tester riceverebbe verifica email o inviti. Con
l'SMTP di una casella (o di un servizio di invio) che accetta di spedire a chiunque, il problema si
aggira **senza verificare il dominio su Resend**.

## Come si sceglie il trasporto
| Variabile | Valori | Effetto |
| --- | --- | --- |
| `MAIL_TRANSPORT` | `auto` (default) | Resend se c'è `RESEND_API_KEY`, altrimenti SMTP: **comportamento di prima** |
| | `smtp` | solo SMTP, **anche con la chiave Resend impostata** (che resta lì, pronta per tornare) |
| | `resend` | solo Resend; senza chiave l'invio fallisce con un errore chiaro |
| `MAIL_FALLBACK_TO_SMTP` | `true` / `false` (default) | se Resend fallisce (es. destinatario rifiutato dalla sandbox) e l'SMTP è configurato, riprova via SMTP |

Consiglio per il pilota: `MAIL_TRANSPORT=smtp`. Per tornare a Resend basta rimettere `auto` (o
`resend`) quando il dominio sarà verificato.

## Variabili SMTP
| Variabile | Esempio | Note |
| --- | --- | --- |
| `SMTP_HOST` | `smtp.tuoprovider.it` | dal tuo provider |
| `SMTP_PORT` | `587` o `465` | 587 = STARTTLS, 465 = TLS implicito |
| `SMTP_USE_TLS` | `true` | per la porta **587** (STARTTLS) |
| `SMTP_USE_SSL` | `true` | per la porta **465** (TLS implicito). **Non** impostarlo insieme a `SMTP_USE_TLS` |
| `SMTP_USER` | `noreply@tuodominio.it` | l'utente della casella/servizio |
| `SMTP_PASSWORD` | *(segreto)* | solo come variabile Railway, mai nel repository |
| `MAIL_FROM` | `noreply@tuodominio.it` | **deve essere un indirizzo che il provider ti autorizza a usare** (di solito lo stesso di `SMTP_USER`), altrimenti il provider rifiuta o manda in spam |
| `MAIL_FROM_NAME` | `FantApperò` | nome mostrato |
| `SMTP_TIMEOUT_SECONDS` | `30` | opzionale |

Il certificato del server viene sempre verificato. Le credenziali non partono mai su una connessione
non cifrata (se mancano sia `SMTP_USE_TLS` sia `SMTP_USE_SSL` l'invio viene rifiutato).

## Cosa devi fare tu (una tantum)
1. **Piano Pro** sul workspace Railway, poi **rifai il deploy** dei servizi: l'SMTP si sblocca solo
   con un deploy nuovo.
2. **Scegli dove inviare**: una casella del tuo dominio (con il provider che lo ospita) oppure un
   servizio di invio con accesso SMTP. Controlla sul suo sito host, porta, modalità (STARTTLS o SSL),
   limiti giornalieri e quale mittente (`MAIL_FROM`) autorizza. Per un pilota piccolo bastano pochi
   invii al giorno, ma verifica il limite del provider.
3. Imposta le variabili sopra nell'ambiente **`pilota`** sul servizio **`worker`**. Le email non
   partono dall'API: l'API le mette in coda (anche quelle scritte dal pannello operatore) e le
   spedisce solo il worker. Sull'API le variabili email non servono.
4. **Verifica dalla rete di Railway** (non dal tuo computer: è lì che la porta può essere bloccata),
   aprendo una shell nel servizio `worker`:
   ```
   python -m mail.diagnostics                       # DNS, connessione, cifratura, login: non invia nulla
   python -m mail.diagnostics --send-to tu@mail.it  # in più invia una email di prova
   ```
   Se la connessione fallisce con un timeout, la diagnosi lo segnala e ricorda la regola del piano
   Pro. Se il login è rifiutato mostra il codice ma mai la password.
5. Prova una registrazione vera con un indirizzo diverso dal tuo e controlla anche la cartella spam.

## Limiti da conoscere
- Inviare da una casella senza **SPF/DKIM** configurati per il dominio del mittente può finire in
  spam presso Gmail/Outlook. Usa gli stessi parametri che il provider ti indica per il tuo dominio.
- I provider di caselle (non di invio massivo) hanno limiti bassi di invii e destinatari: va bene per
  il pilota, meno per un lancio con molti utenti. In quel caso conviene verificare il dominio su
  Resend (o un servizio equivalente) e tornare a `MAIL_TRANSPORT=auto`.

## «Dal pannello risulta inviata ma non arriva nulla»
L'invio è **asincrono**: il pannello registra «inviata» appena l'email è in coda, anche se il worker
poi non riesce a spedirla. L'esito vero sta nei **log del worker** (Railway → worker → Logs):

| Riga nel log del worker | Significato |
| --- | --- |
| `mail_sent via=smtp` | spedita via SMTP: se non arriva guarda lo spam e le regole del provider |
| `mail_sent via=resend` | è partita da Resend, non da SMTP: `MAIL_TRANSPORT` non è `smtp` o c'è ancora `RESEND_API_KEY` in modalità `auto` |
| `mail_send_failed … error=HTTPStatusError` | Resend ha rifiutato (sandbox: solo il titolare dell'account) |
| `mail_send_failed … smtp_host=localhost error=ConnectionRefusedError` | le variabili `SMTP_*` mancano: il worker sta usando il default locale |
| `mail_send_failed … error=SMTPAuthenticationError` | utente o password sbagliati |
| `mail_send_failed … error=TimeoutError` / `OSError` | porta bloccata (piano non Pro, o deploy non rifatto) |
| `Task mail.send_message[…] received` ma nessun `mail_sent` né `mail_send_failed` | l'invio è ancora in corso (timeout di 30 s) o il worker si è riavviato |
| **nessun** `Task mail.send_message[…] received` | il worker non ha ricevuto nulla: l'API non ha accodato (cerca `operator_email_dispatch_failed` nei **log dell'API**) oppure usa un broker diverso dal worker (`REDIS_URL` / `CELERY_BROKER_URL` devono coincidere su `api` e `worker`) |

Se commenti le variabili `SMTP_*` che c'erano già (erano quelle di Resend via SMTP) **devi** impostare
quelle nuove: senza, l'SMTP punta a `localhost` e non parte nulla. Con `MAIL_TRANSPORT=smtp` la chiave
`RESEND_API_KEY` può restare dov'è senza essere usata.
