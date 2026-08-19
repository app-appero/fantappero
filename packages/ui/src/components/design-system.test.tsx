import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Badge } from "./Badge.js";
import { Button } from "./Button.js";
import { Card, CardBody, CardHeader } from "./Card.js";
import { EmptyState } from "./EmptyState.js";
import { Input } from "./Input.js";
import { Modal } from "./Modal.js";
import { Select } from "./Select.js";
import { Skeleton } from "./Skeleton.js";
import { Tab, TabList, TabPanel, Tabs } from "./Tabs.js";
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from "./Table.js";
import { ToastProvider } from "./Toast.js";

describe("Button", () => {
  it("renders variant classes and default type=button", () => {
    const html = renderToStaticMarkup(
      createElement(Button, { variant: "secondary" }, "Azione"),
    );
    expect(html).toContain('class="fa-btn fa-btn--secondary"');
    expect(html).toContain('type="button"');
    expect(html).toContain("Azione");
  });

  it("marks loading state for assistive tech", () => {
    const html = renderToStaticMarkup(createElement(Button, { loading: true }, "Salva"));
    expect(html).toContain('aria-busy="true"');
    expect(html).toContain("fa-btn--loading");
    expect(html).toContain('disabled');
  });

  it("supports disabled state", () => {
    const html = renderToStaticMarkup(createElement(Button, { disabled: true }, "Disabilitato"));
    expect(html).toContain('disabled');
    expect(html).toContain('aria-disabled="true"');
  });
});

describe("Input", () => {
  it("associates label, hint and error with the control", () => {
    const html = renderToStaticMarkup(
      createElement(Input, {
        label: "Email",
        hint: "Usa la tua email",
        error: "Campo obbligatorio",
        name: "email",
      }),
    );
    expect(html).toContain('class="fa-field__label"');
    expect(html).toContain('for="');
    expect(html).toContain('aria-invalid="true"');
    expect(html).toContain('role="alert"');
    expect(html).toContain("Campo obbligatorio");
  });
});

describe("Select", () => {
  it("renders options from props", () => {
    const html = renderToStaticMarkup(
      createElement(Select, {
        label: "Ruolo",
        options: [
          { value: "p", label: "Portiere" },
          { value: "d", label: "Difensore" },
        ],
      }),
    );
    expect(html).toContain('class="fa-select"');
    expect(html).toContain("Portiere");
    expect(html).toContain('value="d"');
  });
});

describe("Card and Badge", () => {
  it("renders card sections", () => {
    const html = renderToStaticMarkup(
      createElement(
        Card,
        null,
        createElement(CardHeader, { title: "Intestazione" }),
        createElement(CardBody, null, "Contenuto"),
      ),
    );
    expect(html).toContain('class="fa-card"');
    expect(html).toContain('class="fa-card__title"');
    expect(html).toContain("Contenuto");
  });

  it("renders badge variants", () => {
    const html = renderToStaticMarkup(createElement(Badge, { variant: "success" }, "Attivo"));
    expect(html).toContain('class="fa-badge fa-badge--success"');
  });
});

describe("Tabs keyboard semantics", () => {
  it("exposes tablist, tab and tabpanel roles", () => {
    const html = renderToStaticMarkup(
      createElement(
        Tabs,
        { defaultValue: "a", "aria-label": "Sezione demo" },
        createElement(
          TabList,
          null,
          createElement(Tab, { value: "a" }, "Primo"),
          createElement(Tab, { value: "b" }, "Secondo"),
        ),
        createElement(TabPanel, { value: "a" }, "Panel A"),
        createElement(TabPanel, { value: "b" }, "Panel B"),
      ),
    );
    expect(html).toContain('role="tablist"');
    expect(html).toContain('role="tab"');
    expect(html).toContain('aria-selected="true"');
    expect(html).toContain('aria-selected="false"');
    expect(html).toContain('role="tabpanel"');
    expect(html).toContain('tabindex="0"');
    expect(html).toContain('tabindex="-1"');
  });
});

describe("Modal", () => {
  it("renders dialog semantics when open", () => {
    const html = renderToStaticMarkup(
      createElement(Modal, {
        open: true,
        title: "Conferma",
        onClose: () => undefined,
      }, "Corpo modale"),
    );
    expect(html).toContain('role="dialog"');
    expect(html).toContain('aria-modal="true"');
    expect(html).toContain("Conferma");
  });

  it("renders nothing when closed", () => {
    const html = renderToStaticMarkup(
      createElement(Modal, {
        open: false,
        title: "Nascosta",
        onClose: () => undefined,
      }, "Corpo"),
    );
    expect(html).toBe("");
  });
});

describe("Table", () => {
  it("renders semantic table structure", () => {
    const html = renderToStaticMarkup(
      createElement(
        Table,
        { compact: true },
        createElement(
          TableHead,
          null,
          createElement(
            TableRow,
            null,
            createElement(TableHeaderCell, null, "Colonna"),
          ),
        ),
        createElement(
          TableBody,
          null,
          createElement(TableRow, null, createElement(TableCell, null, "Valore")),
        ),
      ),
    );
    expect(html).toContain('class="fa-table fa-table--compact"');
    expect(html).toContain('scope="col"');
    expect(html).toContain("Valore");
  });
});

describe("Skeleton and EmptyState", () => {
  it("exposes busy status on skeleton", () => {
    const html = renderToStaticMarkup(createElement(Skeleton, { variant: "title" }));
    expect(html).toContain('role="status"');
    expect(html).toContain('aria-busy="true"');
    expect(html).toContain("fa-skeleton--title");
  });

  it("renders empty state with optional actions slot", () => {
    const html = renderToStaticMarkup(
      createElement(EmptyState, {
        title: "Nessun elemento",
        description: "Aggiungi un elemento per iniziare.",
        actions: createElement(Button, null, "Aggiungi"),
      }),
    );
    expect(html).toContain('data-testid="empty-state"');
    expect(html).toContain("fa-empty-state__actions");
    expect(html).toContain("Aggiungi");
  });
});

describe("ToastProvider", () => {
  it("renders live region container", () => {
    const html = renderToStaticMarkup(
      createElement(ToastProvider, null, createElement("span", null, "App")),
    );
    expect(html).toContain('class="fa-toast-region"');
    expect(html).toContain('aria-live="polite"');
  });
});
