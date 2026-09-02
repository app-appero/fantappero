import { type HTMLAttributes, type ReactNode } from "react";
import { Select, type SelectOption } from "../Select.js";
import { classNames } from "../../utils/classNames.js";

export type LeagueOption = SelectOption;

export type LeagueSelectorProps = Omit<
  HTMLAttributes<HTMLDivElement>,
  "onChange" | "defaultValue"
> & {
  label: string;
  leagues: readonly LeagueOption[];
  value: string;
  onChange: (leagueId: string) => void;
  placeholder?: string;
  hint?: string;
  disabled?: boolean;
  /** Rendered once next to the selector, e.g. a lock countdown for the active league. */
  accessory?: ReactNode;
};

export function LeagueSelector({
  label,
  leagues,
  value,
  onChange,
  placeholder,
  hint,
  disabled,
  accessory,
  className,
  ...rest
}: LeagueSelectorProps) {
  return (
    <div className={classNames("fa-league-selector", className)} {...rest}>
      <Select
        label={label}
        options={[...leagues]}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        hint={hint}
        disabled={disabled}
        data-testid="league-selector"
      />
      {accessory ? <div className="fa-league-selector__accessory">{accessory}</div> : null}
    </div>
  );
}
