import {
  PRIVACY_NOTICE_INTRO,
  PRIVACY_NOTICE_SECTIONS,
  PRIVACY_NOTICE_TITLE,
  PRIVACY_NOTICE_VERSION,
} from "@fantappero/contracts";

import type { MouseEvent } from "react";

import { Link } from "../router/simpleRouter";

/**
 * «← Indietro»: se c'è una pagina precedente (es. accesso, profilo, segnalazioni) ci torna;
 * se l'informativa è stata aperta da fuori (scheda nuova) il link porta all'accesso.
 */
function goBackIfPossible(event: MouseEvent<HTMLAnchorElement>) {
  // Ctrl/Cmd+clic e clic centrale aprono /accedi come un link normale.
  if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
    return;
  }
  if (window.history.length > 1) {
    event.preventDefault();
    window.history.back();
  }
}

/** Informativa privacy del pilota: pubblica (si legge anche prima di accedere). */
export function PrivacyPage() {
  return (
    <main className="fa-privacy" data-testid="privacy-page">
      <article className="fa-privacy__article">
        <p className="fa-privacy__back">
          <Link to="/accedi" data-testid="privacy-back" onClick={goBackIfPossible}>
            ← Indietro
          </Link>
        </p>
        <h1>{PRIVACY_NOTICE_TITLE}</h1>
        <p className="fa-privacy__version" data-testid="privacy-version">
          Versione {PRIVACY_NOTICE_VERSION}
        </p>
        <p>{PRIVACY_NOTICE_INTRO}</p>
        {PRIVACY_NOTICE_SECTIONS.map((section) => (
          <section key={section.id} data-testid={`privacy-section-${section.id}`}>
            <h2>{section.title}</h2>
            {section.paragraphs?.map((text) => <p key={text}>{text}</p>)}
            {section.bullets ? (
              <ul>
                {section.bullets.map((text) => (
                  <li key={text}>{text}</li>
                ))}
              </ul>
            ) : null}
          </section>
        ))}
      </article>
    </main>
  );
}
