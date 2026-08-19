import { parseWireframeState, WIREFRAME_STATES } from "./catalog";
import { useMemo } from "react";
import { useLocation } from "../router/simpleRouter";
import type { UiState } from "@fantappero/ui";

export function parseWireframeStateFromSearch(search: string): UiState {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  return parseWireframeState(params.get("stato")) as UiState;
}

export { WIREFRAME_STATES };

export function useWireframeState(): UiState {
  const { search } = useLocation();
  return useMemo(() => parseWireframeStateFromSearch(search), [search]);
}

export function shouldShowWireframeMeta(search: string): boolean {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  return params.get("meta") === "1";
}

export function useWireframeMetaVisible(): boolean {
  const { search } = useLocation();
  return useMemo(() => shouldShowWireframeMeta(search), [search]);
}
