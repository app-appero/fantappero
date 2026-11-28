import type { RunOutcomeLine, RunTone } from "@fantappero/contracts";

export type RunOutcomeListProps = {
  title: string;
  /** Riga di riepilogo sopra l'elenco (es. «Avviati 8 job su 9»). */
  summary?: string | null;
  tone: RunTone;
  lines: RunOutcomeLine[];
  testId: string;
};

/**
 * Esito di «Esegui» e «Esegui tutti» (1.5): una riga per job o per operazione, con il colore
 * dell'esito (verde riuscito, giallo avviso o saltato, rosso errore). Lo stesso elenco dell'app.
 */
export function RunOutcomeList({ title, summary, tone, lines, testId }: RunOutcomeListProps) {
  return (
    <section
      className={`fa-run-result fa-run-result--${tone}`}
      aria-live="polite"
      data-testid={testId}
    >
      <h3 className="fa-run-result__title">{title}</h3>
      {summary ? (
        <p className="fa-run-result__summary" data-testid={`${testId}-summary`}>
          {summary}
        </p>
      ) : null}
      <ul className="fa-run-result__list">
        {lines.map((line) => (
          <li
            key={line.key}
            className={`fa-run-result__line fa-run-result__line--${line.tone}`}
            data-testid={`${testId}-${line.key}`}
          >
            <strong>{line.title}</strong>
            <span>{line.text}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
