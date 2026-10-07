import { useSyncExternalStore } from "react";
import type { ThemePreference } from "@fantappero/ui/theme";
import { readThemePreference, subscribeThemePreference } from "./colorScheme";

export function useThemePreference(): ThemePreference {
  return useSyncExternalStore(subscribeThemePreference, readThemePreference, () => "system");
}
