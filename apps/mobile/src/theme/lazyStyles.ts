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
        // `T` is already checked against `StyleSheet.create`'s constraint at
        // each `factory()` call site; RN's internal style constraint type
        // isn't exported, so there's no narrower bound to declare here.
        cached = StyleSheet.create(factory() as any) as T;
        cachedId = id;
      }
      return cached[prop];
    },
  });
}
