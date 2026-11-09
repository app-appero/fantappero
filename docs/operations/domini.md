# Dominio `fantappero.it` — sottodomini per dev e pilota

Procedura per collegare `fantappero.it` (DNS su Aruba) ai servizi su Railway. Si fa un ambiente
alla volta: prima **dev** (nessun tester coinvolto, si può sbagliare senza rischio), poi
**pilota** solo dopo aver verificato che dev funziona davvero end-to-end.

Finché questa procedura non è conclusa, gli indirizzi `*.up.railway.app` attuali restano
validi e **non vanno tolti**: si aggiunge il dominio nuovo accanto, si verifica, e solo allora
si smette di usare quello vecchio (mai per i tester già invitati senza un nuovo tag pilota).

## Sottodomini

| Sottodominio | Punta a | Serve a |
| --- | --- | --- |
| `dev.fantappero.it` | servizio web, ambiente dev | sito di sviluppo |
| `api-dev.fantappero.it` | servizio API, ambiente dev | backend di sviluppo |
| `pilota.fantappero.it` | servizio web, ambiente pilota | sito del pilota (sostituisce l'URL Railway nel testo d'invito) |
| `api-pilota.fantappero.it` | servizio API, ambiente pilota | backend del pilota |

## Per ciascun sottodominio

### 1. Railway — chiedere il dominio

Nel servizio giusto (web o API, dev o pilota): **Settings → Networking → Custom Domain** →
inserisci il sottodominio (es. `dev.fantappero.it`). Railway mostra un valore CNAME (qualcosa
come `xxxxx.up.railway.app`) ed eventualmente un record TXT di verifica.

### 2. Aruba — creare il record

Nella gestione DNS di Aruba per `fantappero.it`:

- **Tipo**: CNAME
- **Host**: solo la parte prima del dominio (es. `dev`, non `dev.fantappero.it`)
- **Valore**: esattamente quello mostrato da Railway
- **TTL**: valore di default va bene

Se Railway ha chiesto anche un TXT di verifica, crealo allo stesso modo (tipo TXT, host e
valore come indicati). **Non toccare i record MX**: servono alla posta (`info@globetrotta.it`
passa da lì).

### 3. Aspettare

La propagazione DNS e l'emissione del certificato da parte di Railway possono richiedere da
pochi minuti a qualche ora. Railway mostra il dominio come «Active» quando è pronto; prima di
allora l'indirizzo nuovo può dare errore di certificato, è normale.

### 4. Aggiornare le variabili (solo dopo che Railway mostra «Active»)

**Servizio API** (dev o pilota):
- `WEB_APP_BASE_URL` = `https://dev.fantappero.it` (o `https://pilota.fantappero.it`)

**Servizio web** (dev o pilota), poi **ricostruire** (le variabili `VITE_*` vengono incorporate
nel sito al momento della build, cambiarle da sole non basta):
- `VITE_API_BASE_URL` = `https://api-dev.fantappero.it` (o `https://api-pilota.fantappero.it`)

**App mobile**, solo per il build che useranno i tester del pilota, e serve un **nuovo build**
(anche qui le variabili sono incorporate nell'app, non lette a runtime):
- `EXPO_PUBLIC_API_BASE_URL` = `https://api-pilota.fantappero.it`
- `EXPO_PUBLIC_WEB_BASE_URL` = `https://pilota.fantappero.it`

**Google Cloud Console** (credenziali OAuth del client web, quello usato dal bottone «Accedi
con Google» su sito e, per il mobile, nella pagina di handoff): in **Authorized JavaScript
origins** aggiungi `https://dev.fantappero.it` e, quando tocca al pilota,
`https://pilota.fantappero.it`. Senza questo passaggio il bottone Google smette di funzionare
su quell'indirizzo (errore «redirect_uri_mismatch» o simile), non è legato al codice.

Non serve toccare CORS lato backend: l'API accetta richieste da qualunque origine
(`allow_origins=["*"]`, `allow_credentials=False` — nessun cookie in gioco, solo token nell'header
Authorization, vedi `docs/operations/beta_readiness/ep12-04_security_review.md`).

### 5. Verificare

- Il sito si apre su `https://dev.fantappero.it` (o `pilota.`) con lucchetto verde.
- Login con Google funziona (prova proprio questo: è il passaggio più facile da dimenticare,
  per via del punto Google Cloud sopra).
- Un'azione che chiama l'API (es. aprire una lega) funziona: conferma che `VITE_API_BASE_URL`
  punta al dominio giusto e che quel servizio API è davvero raggiungibile su
  `https://api-dev.fantappero.it` (prova anche diretta: apri quell'indirizzo nel browser, deve
  rispondere, non dare errore di dominio).

## Quando si passa al pilota

Solo dopo aver verificato dev end-to-end. In più, per il pilota:
- aggiorna il link nel testo d'invito (`docs/operations/invito_tester_pilota.md`) da
  `https://fantappero-web-pilot.up.railway.app/` a `https://pilota.fantappero.it/`;
- se ci sono già tester con l'app installata, il cambio di `EXPO_PUBLIC_*` richiede che
  reinstallino un nuovo build (non si aggiorna da solo); valuta se farlo in corrispondenza di un
  nuovo tag `pilota-1.x`, non a metà di una prova in corso, per non confonderli.

## Cosa resta su `railway.app`

Il dominio `fantappero.it` nasconde solo l'indirizzo nella barra del browser. La pagina che
Railway mostra quando si supera la soglia di spesa resta quella di Railway (la serve il loro
bordo rete, non si personalizza da qui): per un messaggio diverso in quel caso serve mettere
Cloudflare davanti, un lavoro a parte, non necessario per avere il dominio proprio.
