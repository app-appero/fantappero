import { type HTMLAttributes } from "react";
import { Card, CardBody } from "../Card.js";
import { classNames } from "../../utils/classNames.js";

export type KpiTrend = "up" | "down" | "neutral";

export type KpiCardProps = HTMLAttributes<HTMLElement> & {
  label: string;
  value: string | number;
  /** Optional delta caption (e.g. "+2.4 vs turno prec."). */
  delta?: string;
  trend?: KpiTrend;
};

export function KpiCard({ label, value, delta, trend = "neutral", className, ...rest }: KpiCardProps) {
  return (
    <Card className={classNames("fa-kpi-card", className)} data-testid="kpi-card" {...rest}>
      <CardBody>
        <p className="fa-kpi-card__label">{label}</p>
        <p className="fa-kpi-card__value">{value}</p>
        {delta ? (
          <p className={classNames("fa-kpi-card__delta", `fa-kpi-card__delta--${trend}`)}>{delta}</p>
        ) : null}
      </CardBody>
    </Card>
  );
}
