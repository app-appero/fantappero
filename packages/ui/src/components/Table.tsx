import { type HTMLAttributes, type TdHTMLAttributes, type ThHTMLAttributes } from "react";
import { classNames } from "../utils/classNames.js";

export type TableProps = HTMLAttributes<HTMLTableElement> & {
  compact?: boolean;
};

export function Table({ compact = false, className, ...rest }: TableProps) {
  return (
    <div className="fa-table-wrap">
      <table
        className={classNames("fa-table", compact && "fa-table--compact", className)}
        {...rest}
      />
    </div>
  );
}

export type TableHeadProps = HTMLAttributes<HTMLTableSectionElement>;

export function TableHead({ className, ...rest }: TableHeadProps) {
  return <thead className={className} {...rest} />;
}

export type TableBodyProps = HTMLAttributes<HTMLTableSectionElement>;

export function TableBody({ className, ...rest }: TableBodyProps) {
  return <tbody className={className} {...rest} />;
}

export type TableRowProps = HTMLAttributes<HTMLTableRowElement>;

export function TableRow({ className, ...rest }: TableRowProps) {
  return <tr className={className} {...rest} />;
}

export type TableHeaderCellProps = ThHTMLAttributes<HTMLTableCellElement>;

export function TableHeaderCell({ className, scope = "col", ...rest }: TableHeaderCellProps) {
  return <th className={className} scope={scope} {...rest} />;
}

export type TableCellProps = TdHTMLAttributes<HTMLTableCellElement>;

export function TableCell({ className, ...rest }: TableCellProps) {
  return <td className={className} {...rest} />;
}
