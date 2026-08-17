import { type HTMLAttributes } from "react";
import { classNames } from "../utils/classNames.js";

export type BadgeVariant = "neutral" | "accent" | "success" | "warning" | "danger";

export type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  variant?: BadgeVariant;
};

/** Same P–D–C–A colors as Rosa: P green, D yellow, C blue, A red. */
export function roleBadgeVariant(role: string | null | undefined): BadgeVariant {
  if (role === "P") {
    return "success";
  }
  if (role === "D") {
    return "warning";
  }
  if (role === "C") {
    return "accent";
  }
  if (role === "A") {
    return "danger";
  }
  return "neutral";
}

export function Badge({ variant = "neutral", className, ...rest }: BadgeProps) {
  return (
    <span className={classNames("fa-badge", `fa-badge--${variant}`, className)} {...rest} />
  );
}
