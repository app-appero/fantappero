# Landing «Lavori in corso» (branch `produzione`)

Pagina statica con invito a diventare tester su <https://pilota.fantappero.it>.

- `build.mjs` genera `public/index.html` e le immagini SVG (`public/img`) con gli stessi generatori dell'app
  (avatar, stemmi e distintivi in `packages/contracts/src/playerAvatar.ts`).
  Dopo aver cambiato nomi o club: `node --experimental-strip-types build.mjs`.
- `public/styles.css` contiene la grafica (responsive, animazioni disattivate con `prefers-reduced-motion`).
- `server.mjs` serve `public/` sulla porta `$PORT` (nessuna dipendenza); `/health` risponde `ok`.

Avvio: `node server.mjs` (o `pnpm --filter @fantappero/landing start`).

I giocatori di esempio sono quelli che a novembre 2026 giocano in uno dei 5 campionati: da ricontrollare
a ogni sessione di mercato.
