import {
  createContext,
  type KeyboardEvent,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { classNames } from "../utils/classNames.js";

type TabsContextValue = {
  activeValue: string;
  setActiveValue: (value: string) => void;
  tabsAriaLabel?: string;
  registerTab: (value: string) => void;
  tabValues: string[];
};

const TabsContext = createContext<TabsContextValue | null>(null);

function useTabsContext(component: string): TabsContextValue {
  const context = useContext(TabsContext);
  if (!context) {
    throw new Error(`${component} must be used within Tabs.`);
  }
  return context;
}

export type TabsProps = {
  children: ReactNode;
  defaultValue?: string;
  value?: string;
  onValueChange?: (value: string) => void;
  className?: string;
  "aria-label"?: string;
};

export function Tabs({
  children,
  defaultValue = "",
  value: controlledValue,
  onValueChange,
  className,
  "aria-label": ariaLabel,
}: TabsProps) {
  const [uncontrolledValue, setUncontrolledValue] = useState(defaultValue);
  const [tabValues, setTabValues] = useState<string[]>([]);
  const activeValue = controlledValue ?? uncontrolledValue;

  const setActiveValue = useCallback(
    (next: string) => {
      if (controlledValue === undefined) {
        setUncontrolledValue(next);
      }
      onValueChange?.(next);
    },
    [controlledValue, onValueChange],
  );

  const registerTab = useCallback((value: string) => {
    setTabValues((current) => (current.includes(value) ? current : [...current, value]));
  }, []);

  useEffect(() => {
    if (!activeValue && tabValues.length > 0 && controlledValue === undefined) {
      setUncontrolledValue(tabValues[0] ?? "");
    }
  }, [activeValue, tabValues, controlledValue]);

  return (
    <TabsContext.Provider
      value={{ activeValue, setActiveValue, tabsAriaLabel: ariaLabel, registerTab, tabValues }}
    >
      <div className={classNames("fa-tabs", className)} data-active-tab={activeValue}>
        {children}
      </div>
    </TabsContext.Provider>
  );
}

export type TabListProps = {
  children: ReactNode;
  className?: string;
};

export function TabList({ children, className }: TabListProps) {
  const { activeValue, setActiveValue, tabsAriaLabel, tabValues } = useTabsContext("TabList");
  const tablistRef = useRef<HTMLDivElement>(null);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const currentIndex = tabValues.indexOf(activeValue);
    if (currentIndex === -1 || tabValues.length === 0) {
      return;
    }

    let nextIndex = currentIndex;
    if (event.key === "ArrowRight") {
      nextIndex = (currentIndex + 1) % tabValues.length;
    } else if (event.key === "ArrowLeft") {
      nextIndex = (currentIndex - 1 + tabValues.length) % tabValues.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = tabValues.length - 1;
    } else {
      return;
    }

    event.preventDefault();
    const nextValue = tabValues[nextIndex];
    if (nextValue !== undefined) {
      setActiveValue(nextValue);
      const button = tablistRef.current?.querySelector<HTMLButtonElement>(
        `#tab-${CSS.escape(nextValue)}`,
      );
      button?.focus();
    }
  };

  return (
    <div
      ref={tablistRef}
      role="tablist"
      aria-label={tabsAriaLabel}
      className={classNames("fa-tablist", className)}
      onKeyDown={onKeyDown}
    >
      {children}
    </div>
  );
}

export type TabProps = {
  value: string;
  children: ReactNode;
  disabled?: boolean;
  className?: string;
};

export function Tab({ value, children, disabled = false, className }: TabProps) {
  const { activeValue, setActiveValue, registerTab } = useTabsContext("Tab");
  const selected = activeValue === value;

  useEffect(() => {
    registerTab(value);
  }, [registerTab, value]);

  return (
    <button
      type="button"
      role="tab"
      id={`tab-${value}`}
      aria-selected={selected}
      aria-controls={`tabpanel-${value}`}
      tabIndex={selected ? 0 : -1}
      disabled={disabled}
      className={classNames("fa-tab", className)}
      onClick={() => setActiveValue(value)}
    >
      {children}
    </button>
  );
}

export type TabPanelProps = {
  value: string;
  children: ReactNode;
  className?: string;
};

export function TabPanel({ value, children, className }: TabPanelProps) {
  const { activeValue } = useTabsContext("TabPanel");
  const selected = activeValue === value;

  return (
    <div
      role="tabpanel"
      id={`tabpanel-${value}`}
      aria-labelledby={`tab-${value}`}
      hidden={!selected}
      tabIndex={selected ? 0 : -1}
      className={classNames("fa-tab-panel", className)}
    >
      {selected ? children : null}
    </div>
  );
}
