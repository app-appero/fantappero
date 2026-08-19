import { type ButtonHTMLAttributes, forwardRef } from "react";
import { classNames } from "../utils/classNames.js";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

export type ButtonProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "disabled"> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  disabled?: boolean;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "primary",
    size = "md",
    loading = false,
    disabled = false,
    className,
    children,
    type = "button",
    ...rest
  },
  ref,
) {
  const isDisabled = disabled || loading;

  return (
    <button
      ref={ref}
      type={type}
      className={classNames(
        "fa-btn",
        `fa-btn--${variant}`,
        size !== "md" && `fa-btn--${size}`,
        loading && "fa-btn--loading",
        className,
      )}
      disabled={isDisabled}
      aria-disabled={isDisabled || undefined}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <span className="fa-btn__spinner" aria-hidden="true" /> : null}
      {children}
    </button>
  );
});
