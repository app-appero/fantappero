import { type TextareaHTMLAttributes, forwardRef, useId } from "react";
import { classNames } from "../utils/classNames.js";

export type TextareaProps = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "id"> & {
  label?: string;
  hint?: string;
  error?: string;
  id?: string;
};

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, hint, error, className, id: idProp, disabled, rows = 5, ...rest },
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
      <textarea
        ref={ref}
        id={id}
        rows={rows}
        className={classNames("fa-input", "fa-textarea", className)}
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
