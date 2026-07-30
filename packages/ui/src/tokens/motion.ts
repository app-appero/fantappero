/** Motion tokens — subtle, premium feel. */

export const motion = {
  duration: {
    instant: 80,
    fast: 150,
    normal: 250,
    slow: 400,
  },
  easing: {
    standard: "cubic-bezier(0.4, 0, 0.2, 1)",
    enter: "cubic-bezier(0, 0, 0.2, 1)",
    exit: "cubic-bezier(0.4, 0, 1, 1)",
  },
} as const;

export type MotionDurationToken = keyof typeof motion.duration;
