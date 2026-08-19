import type { UiState } from "@fantappero/ui";

/** Re-export shared wireframe catalog from contracts (EPUI-04). */
export {
  ALL_MACROFLOWS,
  WIREFRAME_CATALOG,
  WIREFRAME_STATES,
  getWireframeScreen,
  macroflowsCovered,
  parseWireframeState,
} from "@fantappero/contracts";
export type {
  Macroflow,
  WireframeScreenId,
  WireframeScreenMeta,
  WireframeUiState,
} from "@fantappero/contracts";

/** Alias for web consumers that expect UiState from the UI package. */
export type { UiState };
