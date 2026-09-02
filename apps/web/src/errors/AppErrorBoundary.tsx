import { UiStatePanel } from "@fantappero/ui";
import { Component, type ErrorInfo, type ReactNode } from "react";

type AppErrorBoundaryProps = {
  children: ReactNode;
};

type AppErrorBoundaryState = {
  hasError: boolean;
};

/** Catches unexpected render errors and shows a recoverable fallback (EPUI-05). */
export class AppErrorBoundary extends Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
  state: AppErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): AppErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("[AppErrorBoundary]", error.name, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="fa-error-boundary" role="alert">
          <UiStatePanel
            state="error"
            title="Qualcosa è andato storto"
            message="Si è verificato un errore imprevisto. Ricarica la pagina o riprova più tardi."
            testId="app-error-boundary"
          />
        </div>
      );
    }

    return this.props.children;
  }
}
