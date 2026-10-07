import { StyleSheet } from "react-native";
import { getActiveColorScheme } from "@fantappero/ui/theme";

/**
 * Builds a stylesheet the first time a key is read, then again when the
 * color scheme changes. Callers keep using `styles.foo` as before.
 */
export function lazyStyles<T extends Record<string, unknown>>(factory: () => T): T {
  let cachedId = "";
  let cached: T | null = null;
  return new Proxy({} as T, {
    get(_target, prop) {
      if (typeof prop !== "string") {
        return undefined;
      }
      const id = getActiveColorScheme();
      if (!cached || cachedId !== id) {
        cached = StyleSheet.create(factory() as StyleSheet.NamedStyles<any>) as T;
        cachedId = id;
      }
      return cached[prop];
    },
  });
}
