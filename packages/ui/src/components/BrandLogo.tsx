import { type HTMLAttributes } from "react";
import { classNames } from "../utils/classNames.js";

export type BrandLogoVariant = "mark" | "full";
export type BrandLogoSize = "sm" | "md" | "lg";

export type BrandLogoProps = HTMLAttributes<HTMLDivElement> & {
  variant?: BrandLogoVariant;
  size?: BrandLogoSize;
};

function BrandMark({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M16 3.5 26.5 8.5v9.2c0 5.2-4.2 9.8-10.5 11.8C9.7 27.5 5.5 22.9 5.5 17.7V8.5L16 3.5z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <line
        x1="16"
        y1="11"
        x2="16"
        y2="22"
        stroke="currentColor"
        strokeWidth="0.75"
        opacity="0.35"
      />
      <circle cx="16" cy="16.5" r="4.25" stroke="currentColor" strokeWidth="1" opacity="0.55" />
      <path
        d="M12.5 11.5h7.5M12.5 11.5v10M12.5 16h4.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** Presentational brand mark and wordmark (EPUI-04 / EPUI-01). */
export function BrandLogo({
  variant = "full",
  size = "md",
  className,
  ...rest
}: BrandLogoProps) {
  return (
    <div
      className={classNames(
        "fa-brand-logo",
        variant === "mark" && "fa-brand-logo--mark",
        variant === "full" && "fa-brand-logo--full",
        size !== "md" && `fa-brand-logo--${size}`,
        className,
      )}
      data-testid="brand-logo"
      {...rest}
    >
      <BrandMark className="fa-brand-logo__mark" />
      {variant === "full" ? (
        <span className="fa-brand-logo__wordmark">FantApperò</span>
      ) : null}
    </div>
  );
}
