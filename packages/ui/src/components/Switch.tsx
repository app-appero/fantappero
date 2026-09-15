import { classNames } from "../utils/classNames.js";

export type SwitchProps = {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  label?: string;
  ariaLabel?: string;
  /** Visible status text shown next to the control (e.g. Aperto / Chiuso). */
  statusLabel?: string;
  testId?: string;
};

/** Accessible on/off switch used for admin-controlled gates. */
export function Switch({
  checked,
  onCheckedChange,
  disabled = false,
  label,
  ariaLabel,
  statusLabel,
  testId,
}: SwitchProps) {
  return (
    <div className="fa-switch">
      {label ? <span className="fa-switch__label">{label}</span> : null}
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={ariaLabel ?? label}
        disabled={disabled}
        className={classNames("fa-switch__control", checked && "fa-switch__control--on")}
        data-testid={testId}
        onClick={() => onCheckedChange(!checked)}
      >
        <span className="fa-switch__thumb" aria-hidden="true" />
      </button>
      {statusLabel ? <span className="fa-switch__status">{statusLabel}</span> : null}
    </div>
  );
}
