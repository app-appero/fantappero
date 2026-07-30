import { type HTMLAttributes } from "react";
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
};

export function LeagueSelector({
  label,
  leagues,
  value,
  onChange,
  placeholder,
  hint,
  disabled,
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
    </div>
  );
}
