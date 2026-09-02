import { useEffect, useRef, useState, type HTMLAttributes } from "react";
import {
  computeCountdown,
  formatCountdown,
  type LineupLockCountdownState,
} from "@fantappero/contracts";
import { classNames } from "../../utils/classNames.js";

const STATE_LABEL: Record<LineupLockCountdownState, string> = {
  no_active_turn: "Nessun turno attivo",
  turn_not_open: "Turno non ancora aperto",
  no_roster: "Rosa non ancora assegnata",
  no_pending_lock: "Formazione confermata",
  counting_down: "",
};

export type LockCountdownProps = Omit<HTMLAttributes<HTMLDivElement>, "children"> & {
  state: LineupLockCountdownState;
  nextLockAt: string | null;
  /** Injectable clock, for tests; defaults to the real clock, ticking every second. */
  now?: () => Date;
  /** Called once when the ticking countdown reaches zero, to trigger a data refetch. */
  onExpire?: () => void;
};

function defaultClock(): Date {
  return new Date();
}

/** Per-team lock countdown (EP-turni-automazione): counts down locally, refetch of `nextLockAt` is the caller's job. */
export function LockCountdown({
  state,
  nextLockAt,
  now,
  onExpire,
  className,
  ...rest
}: LockCountdownProps) {
  const clock = now ?? defaultClock;
  const active = state === "counting_down" && Boolean(nextLockAt);
  const [tick, setTick] = useState(() => clock());

  useEffect(() => {
    if (!active) {
      return;
    }
    setTick(clock());
    const interval = setInterval(() => setTick(clock()), 1_000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, nextLockAt]);

  const parts = active ? computeCountdown(nextLockAt, tick) : null;

  const onExpireRef = useRef(onExpire);
  onExpireRef.current = onExpire;
  useEffect(() => {
    if (parts?.expired) {
      onExpireRef.current?.();
    }
  }, [parts?.expired]);

  if (!active || !parts) {
    return (
      <div
        className={classNames("fa-lock-countdown", "fa-lock-countdown--idle", className)}
        data-testid="lock-countdown"
        data-state={state}
        {...rest}
      >
        <span className="fa-lock-countdown__label">{STATE_LABEL[state]}</span>
      </div>
    );
  }

  return (
    <div
      className={classNames("fa-lock-countdown", className)}
      data-testid="lock-countdown"
      data-state={state}
      {...rest}
    >
      <span className="fa-lock-countdown__label">Prossimo blocco</span>
      <span className="fa-lock-countdown__value">{formatCountdown(parts)}</span>
    </div>
  );
}
