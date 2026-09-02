import type { WireframeUiState } from "@fantappero/contracts";
import { parseWireframeState } from "@fantappero/contracts";

export function wireframeStateParam(state: WireframeUiState): { stato: WireframeUiState } {
  return { stato: state };
}

export function wireframeStateFromParam(stato: string | undefined): WireframeUiState {
  return parseWireframeState(stato);
}
