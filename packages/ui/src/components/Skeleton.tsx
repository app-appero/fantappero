import { type HTMLAttributes } from "react";
import { classNames } from "../utils/classNames.js";

export type SkeletonVariant = "text" | "title" | "avatar" | "block";

export type SkeletonProps = HTMLAttributes<HTMLSpanElement> & {
  variant?: SkeletonVariant;
  width?: string | number;
  height?: string | number;
};

export function Skeleton({
  variant = "block",
  width,
  height,
  className,
  style,
  "aria-label": ariaLabel = "Caricamento contenuto",
  ...rest
}: SkeletonProps) {
  const resolvedStyle = {
    ...style,
    ...(width !== undefined ? { width: typeof width === "number" ? `${width}px` : width } : {}),
    ...(height !== undefined ? { height: typeof height === "number" ? `${height}px` : height } : {}),
  };

  return (
    <span
      className={classNames(
        "fa-skeleton",
        variant !== "block" && `fa-skeleton--${variant}`,
        className,
      )}
      style={resolvedStyle}
      role="status"
      aria-busy="true"
      aria-label={ariaLabel}
      {...rest}
    />
  );
}
