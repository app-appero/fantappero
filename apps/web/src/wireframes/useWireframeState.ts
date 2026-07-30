import type { UiState } from "@fantappero/ui";
import { useMemo } from "react";
import { useLocation } from "../router/simpleRouter";
import { WIREFRAME_STATES } from "./catalog";

export function parseWireframeState(search: string): UiState {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const stato = params.get("stato");
  if (stato && (WIREFRAME_STATES as readonly string[]).includes(stato)) {
    return stato as UiState;
  }
  return "success";
}

export function useWireframeState(): UiState {
  const { search } = useLocation();
  return useMemo(() => parseWireframeState(search), [search]);
}

export function shouldShowWireframeMeta(search: string): boolean {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  return params.get("meta") === "1";
}

export function useWireframeMetaVisible(): boolean {
  const { search } = useLocation();
  return useMemo(() => shouldShowWireframeMeta(search), [search]);
}
