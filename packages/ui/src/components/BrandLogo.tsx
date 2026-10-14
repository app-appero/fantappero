import { useId, type HTMLAttributes } from "react";
import { classNames } from "../utils/classNames.js";

export type BrandLogoVariant = "mark" | "full";
export type BrandLogoSize = "sm" | "md" | "lg";

export type BrandLogoProps = HTMLAttributes<HTMLDivElement> & {
  variant?: BrandLogoVariant;
  size?: BrandLogoSize;
};

/** Simbolo: "F" in corsa con il pallone, su quadrato con gradiente blu-viola. */
function BrandMark({ className }: { className?: string }) {
  const gradientId = `fa-brand-gradient-${useId().replace(/:/g, "")}`;
  return (
    <svg
      className={className}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <linearGradient
          id={gradientId}
          x1="0"
          y1="0"
          x2="64"
          y2="64"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0" stopColor="#2748d8" />
          <stop offset="1" stopColor="#6a3fe0" />
        </linearGradient>
      </defs>
<rect width="64" height="64" rx="18" fill={`url(#${gradientId})`}/>
      <g opacity=".18">
        <rect x="0" width="8" height="64" fill="#ffffff"/>
        <rect x="16" width="8" height="64" fill="#ffffff"/>
        <rect x="32" width="8" height="64" fill="#ffffff"/>
        <rect x="48" width="8" height="64" fill="#ffffff"/>
      </g>
      <path d="M14 52L20.6 12H49L47.5 20.5H29.2L27.8 28.5H41.8L40.6 35.5H26.6L24.2 52Z" fill="#ffffff"/>
      <circle cx="47" cy="46" r="8.5" fill="#ffd23f"/>
      <path d="M47 42.2L50.7 44.8L49.3 49.1H44.7L43.3 44.8Z" fill="#2748d8"/>
      <path d="M45.5 33L53 27" stroke="#ffd23f" strokeWidth="3.6" strokeLinecap="round"/>
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
