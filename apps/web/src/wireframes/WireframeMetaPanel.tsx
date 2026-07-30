import { Badge } from "@fantappero/ui";
import type { WireframeScreenMeta } from "./catalog";

export type WireframeMetaPanelProps = {
  screen: WireframeScreenMeta;
};

/** PO annotation panel — visible on /dev/wireframes or when ?meta=1. */
export function WireframeMetaPanel({ screen }: WireframeMetaPanelProps) {
  return (
    <aside className="fa-wireframe-meta" data-testid="wireframe-meta-panel">
      <h2 className="fa-wireframe-meta__title">Annotazioni flusso — {screen.title}</h2>
      <dl className="fa-wireframe-meta__list">
        <div>
          <dt>CTA primaria</dt>
          <dd>{screen.primaryCta}</dd>
        </div>
        <div>
          <dt>Informazioni prioritarie</dt>
          <dd>
            <ul>
              {screen.priorityInfo.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </dd>
        </div>
        <div>
          <dt>Passaggi critici</dt>
          <dd>
            <ol>
              {screen.criticalSteps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
          </dd>
        </div>
        <div>
          <dt>Ruoli</dt>
          <dd>{screen.roles.join(" · ")}</dd>
        </div>
        <div>
          <dt>Macroflussi</dt>
          <dd>{screen.macroflows.join(", ")}</dd>
        </div>
      </dl>
      {screen.openDecisions && screen.openDecisions.length > 0 ? (
        <div className="fa-wireframe-meta__tbd">
          <p className="fa-wireframe-meta__tbd-label">Decisioni non approvate</p>
          <ul>
            {screen.openDecisions.map((decision) => (
              <li key={decision}>
                <Badge variant="warning">TBD</Badge> {decision}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </aside>
  );
}
