import { useSyncExternalStore } from "react";

/** Mosse della formazione da mostrare accanto al countdown quando la riga delle mosse esce dalla vista. */
export type MovesDock = { used: number; max: number; draft: number | null } | null;

let current: MovesDock = null;
const listeners = new Set<() => void>();

export function setMovesDock(next: MovesDock): void {
  const same =
    (current === null && next === null) ||
    (current !== null && next !== null && current.used === next.used && current.max === next.max && current.draft === next.draft);
  if (same) {
    return;
  }
  current = next;
  listeners.forEach((listener) => listener());
}

export function useMovesDock(): MovesDock {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    () => current,
    () => null,
  );
}
