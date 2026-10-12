import { useId, type HTMLAttributes } from "react";
import { classNames } from "../utils/classNames.js";

export type BrandLogoVariant = "mark" | "full";
export type BrandLogoSize = "sm" | "md" | "lg";

export type BrandLogoProps = HTMLAttributes<HTMLDivElement> & {
  variant?: BrandLogoVariant;
  size?: BrandLogoSize;
};

/** Simbolo: "F" in corsa con il pallone, su quadrato con gradiente azzurro-menta. */
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
          <stop offset="0" stopColor="#5aa2ff" />
          <stop offset="1" stopColor="#3ddc97" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="18" fill={`url(#${gradientId})`} />
      <path
        d="M16 50L22.1 14H48.5L47.1 22H28.8L27.4 30H40.6L39.4 37H26.2L24 50Z"
        fill="#06121f"
      />
      <circle cx="47" cy="44" r="5" stroke="#06121f" strokeWidth="3" />
      <circle cx="47" cy="44" r="1.6" fill="#06121f" />
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
