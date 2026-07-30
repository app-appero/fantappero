import type { ReactNode } from "react";
import type { WireframeScreenId } from "./catalog";
import { getWireframeScreen } from "./catalog";
import { renderWireframeBody } from "./renderWireframeBody";
import { useWireframeMetaVisible, useWireframeState } from "./useWireframeState";
import { WireframeMetaPanel } from "./WireframeMetaPanel";

export type WireframePageProps = {
  screenId: WireframeScreenId;
  successContent: ReactNode;
  showMeta?: boolean;
};

export function WireframePage({ screenId, successContent, showMeta = false }: WireframePageProps) {
  const screen = getWireframeScreen(screenId);
  const state = useWireframeState();
  const metaFromQuery = useWireframeMetaVisible();
  const body = renderWireframeBody({ screen, state, successContent });

  return (
    <>
      {body}
      {showMeta || metaFromQuery ? <WireframeMetaPanel screen={screen} /> : null}
    </>
  );
}
