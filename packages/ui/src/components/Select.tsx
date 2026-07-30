import { type SelectHTMLAttributes, forwardRef, useId } from "react";
import { classNames } from "../utils/classNames.js";

export type SelectOption = {
  value: string;
  label: string;
  disabled?: boolean;
};

export type SelectProps = Omit<SelectHTMLAttributes<HTMLSelectElement>, "id"> & {
  label?: string;
  hint?: string;
  error?: string;
  options: SelectOption[];
  placeholder?: string;
  id?: string;
};

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  {
    label,
    hint,
    error,
    options,
    placeholder,
    className,
    id: idProp,
    disabled,
    ...rest
  },
  ref,
) {
  const generatedId = useId();
  const id = idProp ?? generatedId;
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;

  return (
    <div className="fa-field">
      {label ? (
        <label className="fa-field__label" htmlFor={id}>
          {label}
        </label>
      ) : null}
      <select
        ref={ref}
        id={id}
        className={classNames("fa-select", className)}
        disabled={disabled}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        {...rest}
      >
        {placeholder ? (
          <option value="" disabled>
            {placeholder}
          </option>
        ) : null}
        {options.map((option) => (
          <option key={option.value} value={option.value} disabled={option.disabled}>
            {option.label}
          </option>
        ))}
      </select>
      {hint && !error ? (
        <p className="fa-field__hint" id={hintId}>
          {hint}
        </p>
      ) : null}
      {error ? (
        <p className="fa-field__error" id={errorId} role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
});
