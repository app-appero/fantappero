import { classNames } from "../utils/classNames.js";

export type ProgressBarProps = {
  percent: number;
  label?: string;
  className?: string;
};

export function ProgressBar({ percent, label, className }: ProgressBarProps) {
  const clamped = Math.max(0, Math.min(100, percent));
  return (
    <div
      className={classNames("fa-progress-bar", className)}
      role="progressbar"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
    >
      <div className="fa-progress-bar__fill" style={{ width: `${clamped}%` }} />
      {label ? <span className="fa-progress-bar__label">{label}</span> : null}
    </div>
  );
}
