import { type HTMLAttributes, type ReactNode } from "react";
import { classNames } from "../../utils/classNames.js";

export type PageContainerProps = HTMLAttributes<HTMLElement> & {
  title?: string;
  /** Optional actions slot (buttons, filters). */
  actions?: ReactNode;
  /** Breadcrumb or other top meta content. */
  header?: ReactNode;
  children: ReactNode;
  /** Comfortable (default) or compact density for fantasy tables. */
  density?: "comfortable" | "compact";
};

export function PageContainer({
  title,
  actions,
  header,
  children,
  density = "comfortable",
  className,
  ...rest
}: PageContainerProps) {
  return (
    <article
      className={classNames(
        "fa-page-container",
        density === "compact" && "fa-page-container--compact",
        className,
      )}
      {...rest}
    >
      {header}
      {(title || actions) && (
        <header className="fa-page-container__header">
          {title ? <h1 className="fa-page-container__title">{title}</h1> : null}
          {actions ? <div className="fa-page-container__actions">{actions}</div> : null}
        </header>
      )}
      <div className="fa-page-container__body">{children}</div>
    </article>
  );
}
