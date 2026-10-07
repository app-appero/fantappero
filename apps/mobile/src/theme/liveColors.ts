export function liveStringMap<K extends string>(factory: () => Record<K, string>): Record<K, string> {
  return new Proxy({} as Record<K, string>, {
    get(_target, prop) {
      if (typeof prop !== "string") {
        return undefined;
      }
      return factory()[prop as K];
    },
  });
}

export function livePairMap<K extends string>(
  factory: () => Record<K, { background: string; text: string }>,
): Record<K, { background: string; text: string }> {
  return new Proxy({} as Record<K, { background: string; text: string }>, {
    get(_target, prop) {
      if (typeof prop !== "string") {
        return undefined;
      }
      return factory()[prop as K];
    },
  });
}
