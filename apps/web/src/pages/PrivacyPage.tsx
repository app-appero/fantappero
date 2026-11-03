import {
  PRIVACY_NOTICE_INTRO,
  PRIVACY_NOTICE_SECTIONS,
  PRIVACY_NOTICE_TITLE,
  PRIVACY_NOTICE_VERSION,
} from "@fantappero/contracts";

import { Link } from "../router/simpleRouter";

/** Informativa privacy del pilota: pubblica (si legge anche prima di accedere). */
export function PrivacyPage() {
  return (
    <main className="fa-privacy" data-testid="privacy-page">
      <article className="fa-privacy__article">
        <p>
          <Link to="/accedi" data-testid="privacy-back">
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
