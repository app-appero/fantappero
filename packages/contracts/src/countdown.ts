/** Pure countdown counting/formatting shared by web and mobile (EP-turni-automazione). No network or timer dependency here — callers own the tick. */

export interface CountdownParts {
  totalMs: number;
  days: number;
  hours: number;
  minutes: number;
  seconds: number;
  expired: boolean;
}

function toMs(value: string | Date): number {
  return typeof value === "string" ? new Date(value).getTime() : value.getTime();
}

/** Time remaining from `now` to `targetAt`, clamped at zero. Null when there is no target to count down to. */
export function computeCountdown(
  targetAt: string | Date | null | undefined,
  now: string | Date,
): CountdownParts | null {
  if (!targetAt) {
    return null;
  }
  const targetMs = toMs(targetAt);
  const nowMs = toMs(now);
  const expired = targetMs <= nowMs;
  const totalMs = expired ? 0 : targetMs - nowMs;
  const totalSeconds = Math.floor(totalMs / 1000);
  const days = Math.floor(totalSeconds / 86_400);
  const hours = Math.floor((totalSeconds % 86_400) / 3_600);
  const minutes = Math.floor((totalSeconds % 3_600) / 60);
  const seconds = totalSeconds % 60;
  return { totalMs, days, hours, minutes, seconds, expired };
}

function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

/** "HH:MM:SS" under 24h, "Ng HH:MM:SS" from a day onward — seconds always shown. Empty string when there is nothing to show. */
export function formatCountdown(parts: CountdownParts | null): string {
  if (!parts) {
    return "";
  }
  const clock = `${pad2(parts.hours)}:${pad2(parts.minutes)}:${pad2(parts.seconds)}`;
  if (parts.days > 0) {
    return `${parts.days}g ${clock}`;
  }
  return clock;
}
