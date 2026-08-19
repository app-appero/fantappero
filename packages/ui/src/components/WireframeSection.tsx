import { type ReactNode } from "react";
import { classNames } from "../utils/classNames.js";

export type WireframeSectionProps = {
  /** Region label shown to PO reviewers (Italian copy from apps). */
  label: string;
  children: ReactNode;
  className?: string;
  testId?: string;
};

/** Annotated wireframe region for PO validation (EPUI-04). */
export function WireframeSection({ label, children, className, testId }: WireframeSectionProps) {
  return (
    <section
      className={classNames("fa-wireframe-section", className)}
      data-wireframe-region={label}
      data-testid={testId}
    >
      <header className="fa-wireframe-section__label">{label}</header>
      <div className="fa-wireframe-section__body">{children}</div>
    </section>
  );
}
