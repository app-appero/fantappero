import { Link } from "../router/simpleRouter";
import { WIREFRAME_CATALOG, WIREFRAME_STATES } from "../wireframes/catalog";
import { PageContainer } from "@fantappero/ui";

/** PO hub for EPUI-04 wireframe validation. */
export function WireframesHubPage() {
  return (
    <PageContainer title="Wireframe (dev)">
      <p className="fa-wireframe-hub__intro">
        Hub di validazione EPUI-04 — ogni schermata supporta{" "}
        <code>?stato=loading|empty|error|success|forbidden</code> e{" "}
        <code>?meta=1</code> per le annotazioni flusso.
      </p>
      <ul className="fa-wireframe-hub__list">
        {WIREFRAME_CATALOG.map((screen) => (
          <li key={screen.id} className="fa-wireframe-hub__item">
            <h2>{screen.title}</h2>
            <p>
              Route: <Link to={screen.route}>{screen.route}</Link> · Macroflussi:{" "}
              {screen.macroflows.join(", ")}
            </p>
            <p>CTA primaria: {screen.primaryCta}</p>
            <div className="fa-wireframe-hub__states">
              {WIREFRAME_STATES.map((state) => (
                <Link
                  key={state}
                  to={`${screen.route}?stato=${state}&meta=1`}
                  className="fa-wireframe-hub__state-link"
                >
                  {state}
                </Link>
              ))}
            </div>
          </li>
        ))}
      </ul>
    </PageContainer>
  );
}
