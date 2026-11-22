import type {
  AdminListoneProviderRolesResult,
  AdminListoneRefreshResult,
} from "@fantappero/contracts";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const startRefreshMock = vi.fn();
const fetchAdminListoneMock = vi.fn();
const updateRolesMock = vi.fn();

vi.mock("../admin/ListoneRefreshContext", () => ({
  useListoneRefresh: () => ({
    refreshing: false,
    progress: null,
    seasonYear: null,
    startRefresh: (...args: unknown[]) => startRefreshMock(...args),
  }),
}));
vi.mock("../api/admin", () => ({
  fetchAdminListone: (...args: unknown[]) => fetchAdminListoneMock(...args),
  updateAdminListoneRolesFromProvider: (...args: unknown[]) => updateRolesMock(...args),
  restoreAdminListoneRoles: vi.fn(),
}));
vi.mock("../auth/sessionStorage", () => ({
  loadStoredSession: () => ({ accessToken: "token-op" }),
}));
vi.mock("../auth/AuthContext", () => ({
  getApiErrorMessage: (_error: unknown, fallback: string) => fallback,
}));

import { AdminListonePage } from "./AdminListonePage";

const YEAR = new Date().getFullYear();

const COUNTERS = {
  athletesCreated: 0,
  athletesUpdated: 0,
  membershipsCreated: 0,
  membershipsUpdated: 0,
  transfersCreated: 0,
  listoneCreated: 2,
  listoneUpdated: 5,
  listoneUnchanged: 100,
  listoneSkippedUnmapped: 0,
  roleChangesSkipped: 3,
  catalogSynced: true,
};

const PREVIEW: AdminListoneProviderRolesResult = {
  seasonYear: YEAR,
  dryRun: true,
  entries: [
    {
      athleteId: "ath-1",
      name: "M. Mezzala",
      club: "Napoli",
      currentRole: "C",
      newRole: "A",
      providerPositionRaw: "Attacker",
      inRosters: ["Lega Pilota", "Lega Amici"],
    },
  ],
  counts: {
    changes: 1,
    applied: 0,
    rostersOverQuotaNow: 0,
    rostersOverQuotaAfter: 2,
    rostersResynced: 0,
  },
};

function refreshResult(roleChanges: AdminListoneProviderRolesResult | null) {
  return {
    seasonYear: YEAR,
    mappingVersion: "v1.0.0",
    refreshedAt: "2026-11-22T10:00:00Z",
    message: roleChanges ? "Listone aggiornato. Controlla i ruoli." : "Listone aggiornato.",
    counters: COUNTERS,
    roleChanges,
  } satisfies AdminListoneRefreshResult;
}

describe("«Aggiorna listone»: scelta dei ruoli nella finestra (operatore, 22/11)", () => {
  let container: HTMLDivElement;
  let root: Root;

  const byTestId = (id: string) => document.querySelector<HTMLElement>(`[data-testid="${id}"]`);

  async function click(id: string) {
    const element = byTestId(id);
    expect(element, id).not.toBeNull();
    await act(async () => {
      element?.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
  }

  beforeEach(async () => {
    startRefreshMock.mockReset();
    updateRolesMock.mockReset();
    fetchAdminListoneMock.mockReset();
    fetchAdminListoneMock.mockResolvedValue([]);
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    await act(async () => {
      root.render(createElement(AdminListonePage));
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("di default aggiunge i nuovi calciatori e lascia i ruoli come sono", async () => {
    await click("admin-listone-refresh");
    const choice = byTestId("admin-listone-refresh-choice");
    expect(choice?.textContent).toContain("Aggiungi i nuovi calciatori e aggiorna le squadre");
    expect(choice?.textContent).toContain("Aggiorna anche i ruoli dal fornitore");
    expect((byTestId("admin-listone-refresh-mode-keep") as HTMLInputElement).checked).toBe(true);
    expect(byTestId("admin-listone-refresh-roles-warning")).toBeNull();
    expect(startRefreshMock).not.toHaveBeenCalled();

    startRefreshMock.mockResolvedValueOnce(refreshResult(null));
    await click("admin-listone-refresh-start");

    expect(startRefreshMock).toHaveBeenCalledWith("token-op", YEAR, { updateRoles: false });
    expect(byTestId("admin-listone-refresh-choice")).toBeNull();
    expect(byTestId("admin-listone-refresh-success")?.textContent).toContain(
      "Ruoli lasciati com'erano (il fornitore ne indica un altro): 3",
    );
    expect(byTestId("admin-listone-role-preview")).toBeNull();
    expect(updateRolesMock).not.toHaveBeenCalled();
  });

  it("«Aggiorna anche i ruoli» avvisa, mostra l'anteprima e applica solo dopo la conferma", async () => {
    await click("admin-listone-refresh");
    await click("admin-listone-refresh-mode-roles");
    expect(byTestId("admin-listone-refresh-roles-warning")?.textContent).toContain(
      "Alcuni calciatori possono cambiare ruolo e le rose che li hanno possono andare fuori quota.",
    );

    startRefreshMock.mockResolvedValueOnce(refreshResult(PREVIEW));
    await click("admin-listone-refresh-start");
    expect(startRefreshMock).toHaveBeenCalledWith("token-op", YEAR, { updateRoles: true });

    const row = byTestId("admin-listone-role-preview-row-ath-1");
    expect(row?.textContent).toContain("M. Mezzala");
    expect(row?.textContent).toContain("Napoli");
    expect(row?.textContent).toContain("Lega Pilota, Lega Amici");
    expect(byTestId("admin-listone-role-preview-summary")?.textContent).toContain(
      "con i nuovi ruoli 2",
    );
    // Nessun ruolo applicato finché non si conferma.
    expect(updateRolesMock).not.toHaveBeenCalled();

    updateRolesMock.mockResolvedValueOnce({
      ...PREVIEW,
      dryRun: false,
      counts: { ...PREVIEW.counts, applied: 1, rostersResynced: 2 },
    });
    await click("admin-listone-role-preview-confirm");

    expect(updateRolesMock).toHaveBeenCalledWith("token-op", {
      seasonYear: YEAR,
      dryRun: false,
      athleteIds: ["ath-1"],
    });
    expect(byTestId("admin-listone-role-preview")).toBeNull();
    expect(byTestId("admin-listone-refresh-success")?.textContent).toContain(
      "Ruoli aggiornati dal fornitore: 1. Rose ricalcolate: 2.",
    );
  });

  it("annullando l'anteprima i ruoli restano come sono", async () => {
    await click("admin-listone-refresh");
    await click("admin-listone-refresh-mode-roles");
    startRefreshMock.mockResolvedValueOnce(refreshResult(PREVIEW));
    await click("admin-listone-refresh-start");

    await click("admin-listone-role-preview-cancel");

    expect(updateRolesMock).not.toHaveBeenCalled();
    expect(byTestId("admin-listone-role-preview")).toBeNull();
    expect(byTestId("admin-listone-refresh-success")?.textContent).toContain(
      "Ruoli lasciati come sono",
    );
  });
});
