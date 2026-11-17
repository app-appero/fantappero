import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

type Callback = (response: { credential: string }) => void;

describe("renderGoogleButton", () => {
  const initialize = vi.fn<(config: { client_id: string; callback: Callback }) => void>();
  const renderButton = vi.fn();

  beforeEach(() => {
    vi.resetModules();
    initialize.mockReset();
    renderButton.mockReset();
    window.google = { accounts: { id: { initialize, renderButton } } };
  });

  afterEach(() => {
    delete window.google;
  });

  it("initializes GIS once per client id but redraws the button every time", async () => {
    const { renderGoogleButton } = await import("./googleIdentity");
    const container = document.createElement("div");

    await renderGoogleButton(container, "client-a", () => {});
    await renderGoogleButton(container, "client-a", () => {});

    expect(initialize).toHaveBeenCalledTimes(1);
    expect(renderButton).toHaveBeenCalledTimes(2);

    await renderGoogleButton(container, "client-b", () => {});
    expect(initialize).toHaveBeenCalledTimes(2);
    expect(initialize.mock.calls[1]?.[0].client_id).toBe("client-b");
  });

  it("hands the credential to the latest handler", async () => {
    const { renderGoogleButton } = await import("./googleIdentity");
    const container = document.createElement("div");
    const first = vi.fn();
    const second = vi.fn();

    await renderGoogleButton(container, "client-a", first);
    await renderGoogleButton(container, "client-a", second);

    const callback = initialize.mock.calls[0]?.[0].callback;
    callback?.({ credential: "id-token" });

    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledWith("id-token");
  });
});
