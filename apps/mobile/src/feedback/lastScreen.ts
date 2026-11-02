/**
 * Ultima schermata vista prima di «Segnala un problema»: viaggia con la
 * segnalazione come contesto, così il tester non deve ricordarla.
 */
let lastScreen: string | undefined;

export function rememberLastScreen(name: string | undefined): void {
  if (name && name !== "Feedback") {
    lastScreen = name;
  }
}

export function readLastScreen(): string | undefined {
  return lastScreen;
}
