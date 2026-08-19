import { useRoute } from "@react-navigation/core";
import { wireframeStateFromParam } from "./wireframeStateHelpers";
import type { WireframeUiState } from "@fantappero/contracts";

type WireframeRouteParams = {
  stato?: string;
};

export function useWireframeState(): WireframeUiState {
  const route = useRoute();
  const params = (route.params ?? {}) as WireframeRouteParams;
  return wireframeStateFromParam(params.stato);
}

export { wireframeStateParam } from "./wireframeStateHelpers";
