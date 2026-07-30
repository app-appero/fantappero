import { type HTMLAttributes } from "react";
import { classNames } from "../utils/classNames.js";

export type BadgeVariant = "neutral" | "accent" | "success" | "warning" | "danger";

export type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  variant?: BadgeVariant;
};

export function Badge({ variant = "neutral", className, ...rest }: BadgeProps) {
  return (
    <span className={classNames("fa-badge", `fa-badge--${variant}`, className)} {...rest} />
  );
}
