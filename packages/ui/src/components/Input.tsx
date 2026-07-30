import { type InputHTMLAttributes, forwardRef, useId } from "react";
import { classNames } from "../utils/classNames.js";

export type InputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "id"> & {
  label?: string;
  hint?: string;
  error?: string;
  id?: string;
};

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, hint, error, className, id: idProp, disabled, ...rest },
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
      <input
        ref={ref}
        id={id}
        className={classNames("fa-input", className)}
        disabled={disabled}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        {...rest}
      />
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
