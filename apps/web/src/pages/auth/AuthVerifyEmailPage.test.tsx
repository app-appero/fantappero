import { act, createElement, StrictMode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "../../router/simpleRouter";

const verifyEmailMock = vi.fn();

vi.mock("../../api/auth", () => ({
  verifyEmail: (...args: unknown[]) => verifyEmailMock(...args),
}));

import { AuthVerifyEmailPage } from "./AuthPages";

describe("AuthVerifyEmailPage (single-use token)", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    verifyEmailMock.mockReset();
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
  });

  it("sends the verification token exactly once even under StrictMode's double effect invocation", async () => {
    verifyEmailMock.mockResolvedValue({ message: "Email verificata." });

    await act(async () => {
      root.render(
        createElement(
          StrictMode,
          null,
          createElement(MemoryRouter, {
            initialEntries: ["/verifica-email?token=abc123"],
            children: createElement(AuthVerifyEmailPage),
          }),
        ),
      );
    });
    // Flush the mocked promise's .then()/.finally() chain into a committed
    // render before asserting on the final displayed text.
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(verifyEmailMock).toHaveBeenCalledTimes(1);
    expect(verifyEmailMock).toHaveBeenCalledWith({ token: "abc123" });
    expect(container.textContent).toContain("Email verificata.");
  });
});
