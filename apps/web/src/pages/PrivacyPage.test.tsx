import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { PRIVACY_CONTACT_EMAIL } from "@fantappero/contracts";

import { PrivacyPage } from "./PrivacyPage";
import { MemoryRouter } from "../router/simpleRouter";

describe("PrivacyPage", () => {
  it("mostra versione, contatto e tutte le sezioni dell'informativa", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={["/privacy"]}>
        <PrivacyPage />
      </MemoryRouter>,
    );
    expect(html).toContain('data-testid="privacy-page"');
    expect(html).toContain("2026-11");
    expect(html).toContain(PRIVACY_CONTACT_EMAIL);
    for (const id of ["dati", "finalita", "diritti", "eta"]) {
      expect(html).toContain(`data-testid="privacy-section-${id}"`);
    }
    expect(html).toContain("Segnalazioni");
    expect(html).toContain("Google");
  });
});
