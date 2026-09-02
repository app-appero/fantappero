import { type HTMLAttributes } from "react";
import { Badge, type BadgeVariant } from "../Badge.js";
import { classNames } from "../../utils/classNames.js";

export type AnomalySeverity = "info" | "warning" | "critical";

export type AnomalyIndicatorProps = HTMLAttributes<HTMLDivElement> & {
  severity: AnomalySeverity;
  /** Localized severity caption supplied by the app. */
  severityLabel: string;
  message: string;
  detail?: string;
};

const SEVERITY_VARIANT: Record<AnomalySeverity, BadgeVariant> = {
  info: "accent",
  warning: "warning",
  critical: "danger",
};

export function AnomalyIndicator({
  severity,
  severityLabel,
  message,
  detail,
  className,
  ...rest
}: AnomalyIndicatorProps) {
  return (
    <div
      className={classNames("fa-anomaly", `fa-anomaly--${severity}`, className)}
      role="status"
      data-testid="anomaly-indicator"
      {...rest}
    >
      <Badge variant={SEVERITY_VARIANT[severity]}>{severityLabel}</Badge>
      <p className="fa-anomaly__message">{message}</p>
      {detail ? <p className="fa-anomaly__detail">{detail}</p> : null}
    </div>
  );
}
