/** Stacking layers — use instead of magic z-index values in features. */

export const zIndex = {
  base: 0,
  raised: 10,
  dropdown: 100,
  sticky: 200,
  overlay: 300,
  modal: 400,
  toast: 500,
  tooltip: 600,
} as const;

export type ZIndexToken = keyof typeof zIndex;
