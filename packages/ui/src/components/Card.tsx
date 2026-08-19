import { type HTMLAttributes, type ReactNode } from "react";
import { classNames } from "../utils/classNames.js";

export type CardProps = HTMLAttributes<HTMLElement> & {
  children: ReactNode;
};

export function Card({ className, children, ...rest }: CardProps) {
  return (
    <section className={classNames("fa-card", className)} {...rest}>
      {children}
    </section>
  );
}

export type CardHeaderProps = HTMLAttributes<HTMLDivElement> & {
  title?: string;
  children?: ReactNode;
};

export function CardHeader({ title, children, className, ...rest }: CardHeaderProps) {
  return (
    <header className={classNames("fa-card__header", className)} {...rest}>
      {title ? <h3 className="fa-card__title">{title}</h3> : null}
      {children}
    </header>
  );
}

export type CardBodyProps = HTMLAttributes<HTMLDivElement>;

export function CardBody({ className, ...rest }: CardBodyProps) {
  return <div className={classNames("fa-card__body", className)} {...rest} />;
}

export type CardFooterProps = HTMLAttributes<HTMLDivElement>;

export function CardFooter({ className, ...rest }: CardFooterProps) {
  return <footer className={classNames("fa-card__footer", className)} {...rest} />;
}
