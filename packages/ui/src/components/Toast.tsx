import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";
import { classNames } from "../utils/classNames.js";
import { Button } from "./Button.js";

export type ToastVariant = "info" | "success" | "warning" | "danger";

export type ToastInput = {
  id?: string;
  title: string;
  message?: string;
  variant?: ToastVariant;
  durationMs?: number;
};

type ToastRecord = ToastInput & { id: string };

type ToastContextValue = {
  push: (toast: ToastInput) => string;
  dismiss: (id: string) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within ToastProvider.");
  }
  return context;
}

export type ToastProviderProps = {
  children: ReactNode;
  dismissLabel?: string;
};

export function ToastProvider({ children, dismissLabel = "Chiudi notifica" }: ToastProviderProps) {
  const [toasts, setToasts] = useState<ToastRecord[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const push = useCallback(
    (toast: ToastInput) => {
      const id = toast.id ?? `toast-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      const record: ToastRecord = { ...toast, id };
      setToasts((current) => [...current, record]);

      const duration = toast.durationMs ?? 5000;
      if (typeof window !== "undefined" && duration > 0) {
        window.setTimeout(() => dismiss(id), duration);
      }

      return id;
    },
    [dismiss],
  );

  const value = useMemo(() => ({ push, dismiss }), [push, dismiss]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="fa-toast-region" aria-live="polite" aria-relevant="additions">
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} dismissLabel={dismissLabel} onDismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

type ToastItemProps = {
  toast: ToastRecord;
  dismissLabel: string;
  onDismiss: (id: string) => void;
};

function ToastItem({ toast, dismissLabel, onDismiss }: ToastItemProps) {
  const variant = toast.variant ?? "info";

  return (
    <article
      className={classNames("fa-toast", `fa-toast--${variant}`)}
      role="status"
      aria-atomic="true"
    >
      <div>
        <p className="fa-toast__title">{toast.title}</p>
        {toast.message ? <p className="fa-toast__message">{toast.message}</p> : null}
      </div>
      <Button
        variant="ghost"
        size="sm"
        className="fa-toast__dismiss"
        aria-label={dismissLabel}
        onClick={() => onDismiss(toast.id)}
      >
        ×
      </Button>
    </article>
  );
}
