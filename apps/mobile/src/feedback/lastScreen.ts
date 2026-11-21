/**
 * Ultima schermata vista prima di «Segnala un problema»: viaggia con la
 * segnalazione come contesto, così il tester non deve ricordarla.
 *
 * Si aggiorna dal `NavigationContainer` radice a ogni cambio di schermata. Se la
 * schermata non si conosce si dimentica quella vecchia: meglio nessuna pagina che
 * una sbagliata.
 */
let lastScreen: string | undefined;

export function rememberLastScreen(name: string | undefined): void {
  // «Segnala un problema» non è il contesto di sé stessa: resta la schermata di prima.
  if (name === "Feedback") {
    return;
  }
  lastScreen = name;
}

export function readLastScreen(): string | undefined {
  return lastScreen;
}
