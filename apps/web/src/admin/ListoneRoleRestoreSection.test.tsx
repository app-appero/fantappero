import type { AdminListoneRoleRestoreResult } from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const restoreMock = vi.fn();

vi.mock("../api/admin", () => ({
  restoreAdminListoneRoles: (...args: unknown[]) => restoreMock(...args),
}));
vi.mock("../auth/sessionStorage", () => ({
  loadStoredSession: () => ({ accessToken: "token-op" }),
}));
vi.mock("../auth/AuthContext", () => ({
  getApiErrorMessage: (_error: unknown, fallback: string) => fallback,
}));

import {
  DEFAULT_RESTORE_BEFORE,
  ListoneRoleRestoreSection,
  romeLocalToIso,
} from "./ListoneRoleRestoreSection";

const PREVIEW: AdminListoneRoleRestoreResult = {
  seasonYear: 2026,
  before: "2026-11-21T11:00:00Z",
  dryRun: true,
  entries: [
    {
      athleteId: "ath-1",
      name: "M. Mezzala",
      club: "Napoli",
      currentRole: "A",
      restoredRole: "C",
      reconstructible: true,
      restoredPosition: "Midfielder",
      restoredClub: "Lazio",
      restoredSource: "squads",
      inRosters: ["Lega Pilota"],
    },
    {
      athleteId: "ath-2",
      name: "S. Sconosciuto",
      club: "Lazio",
      currentRole: "D",
      restoredRole: null,
      reconstructible: false,
      restoredPosition: null,
      restoredClub: null,
      restoredSource: null,
      inRosters: [],
    },
  ],
  counts: {
    toRestore: 1,
    notReconstructible: 1,
    restored: 0,
    rostersOverQuotaNow: 2,
    rostersOverQuotaAfter: 0,
    rostersResynced: 0,
  },
};

const APPLIED: AdminListoneRoleRestoreResult = {
  ...PREVIEW,
  dryRun: false,
  counts: { ...PREVIEW.counts, restored: 1, rostersResynced: 2 },
};

describe("Ripristina i ruoli cambiati da un aggiornamento (pannello operatore)", () => {
  let container: HTMLDivElement;
  let root: Root;
  const onRestored = vi.fn();

  const byTestId = (id: string) => container.querySelector<HTMLElement>(`[data-testid="${id}"]`);

  async function click(id: string) {
    await act(async () => {
      byTestId(id)?.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
  }

  beforeEach(async () => {
    restoreMock.mockReset();
    onRestored.mockReset();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    await act(async () => {
      root.render(createElement(ListoneRoleRestoreSection, { seasonYear: 2026, onRestored }));
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("l'ora scelta vale come ora di Roma, con l'ora legale giusta", () => {
    expect(DEFAULT_RESTORE_BEFORE).toBe("2026-11-21T12:00");
    expect(romeLocalToIso("2026-11-21T12:00")).toBe("2026-11-21T11:00:00.000Z");
    expect(romeLocalToIso("2026-07-01T12:00")).toBe("2026-07-01T10:00:00.000Z");
    expect(romeLocalToIso("non è una data")).toBeNull();
  });

  it("mostra cosa cambia, poi ripristina solo dopo la conferma", async () => {
    expect(byTestId("admin-listone-restore")?.textContent).toContain(
      "Ripristina i ruoli cambiati da un aggiornamento",
    );
    const input = container.querySelector<HTMLInputElement>(
      'input[name="admin-listone-restore-before"]',
    );
    expect(input?.type).toBe("datetime-local");
    expect(input?.value).toBe("2026-11-21T12:00");
    expect(input?.classList.contains("fa-input")).toBe(true);

    restoreMock.mockResolvedValueOnce(PREVIEW);
    await click("admin-listone-restore-preview");
    expect(restoreMock).toHaveBeenCalledWith("token-op", {
      seasonYear: 2026,
      before: "2026-11-21T11:00:00.000Z",
      dryRun: true,
      athleteIds: undefined,
    });
    const row = byTestId("admin-listone-restore-row-ath-1");
    expect(row?.textContent).toContain("M. Mezzala");
    expect(row?.textContent).toContain("Napoli");
    expect(row?.textContent).toContain("A");
    expect(row?.textContent).toContain("C");
    expect(row?.textContent).toContain("Lega Pilota");
    // Ruolo di prima preso dalla rosa di un altro club (membership cambiata il 21/11).
    expect(row?.textContent).toContain("(rosa Lazio)");
    expect(byTestId("admin-listone-restore-row-ath-2")?.textContent).toContain(
      "non ricostruibile",
    );
    expect(byTestId("admin-listone-restore-summary")?.textContent).toContain("Da ripristinare: 1");

    // «Ripristina» chiede conferma nella pagina, senza ancora scrivere nulla.
    await click("admin-listone-restore-apply");
    expect(byTestId("admin-listone-restore-confirm")?.textContent).toContain("Confermi?");
    expect(restoreMock).toHaveBeenCalledTimes(1);

    // «Annulla» chiude la conferma.
    await click("admin-listone-restore-confirm-no");
    expect(byTestId("admin-listone-restore-confirm")).toBeNull();
    expect(restoreMock).toHaveBeenCalledTimes(1);

    await click("admin-listone-restore-apply");
    restoreMock.mockResolvedValueOnce(APPLIED);
    await click("admin-listone-restore-confirm-yes");
    expect(restoreMock).toHaveBeenLastCalledWith("token-op", {
      seasonYear: 2026,
      before: "2026-11-21T11:00:00.000Z",
      dryRun: false,
      athleteIds: ["ath-1"],
    });
    expect(byTestId("admin-listone-restore-done")?.textContent).toContain(
      "Ruoli ripristinati: 1",
    );
    expect(onRestored).toHaveBeenCalledTimes(1);
  });

  it("senza nulla da ripristinare «Ripristina» resta disattivato", async () => {
    restoreMock.mockResolvedValueOnce({
      ...PREVIEW,
      entries: [],
      counts: { ...PREVIEW.counts, toRestore: 0, notReconstructible: 0 },
    });
    await click("admin-listone-restore-preview");
    expect(byTestId("admin-listone-restore-empty")?.textContent).toContain(
      "21/11/2026 alle 12:00",
    );
    expect((byTestId("admin-listone-restore-apply") as HTMLButtonElement).disabled).toBe(true);
  });
});
