import { lazyStyles } from "../theme/lazyStyles";
import { Component, type ErrorInfo, type ReactNode } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { theme } from "@fantappero/ui/theme";
import { UiStatePanel } from "../components/UiStatePanel";

const { colors } = theme;

type AppErrorBoundaryProps = {
  children: ReactNode;
};

type AppErrorBoundaryState = {
  hasError: boolean;
  /** Dettaglio tecnico mostrato in piccolo: con uno screenshot si capisce subito la causa. */
  detail: string | null;
};

/** Catches unexpected render errors and shows a recoverable fallback (EPUI-06). */
export class AppErrorBoundary extends Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
  state: AppErrorBoundaryState = { hasError: false, detail: null };

  static getDerivedStateFromError(error: unknown): AppErrorBoundaryState {
    const message = error instanceof Error ? `${error.name}: ${error.message}` : String(error);
    return { hasError: true, detail: message.slice(0, 300) };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("[AppErrorBoundary]", error.name, error.message, info.componentStack);
    const where = String(info.componentStack ?? "")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .slice(0, 3)
      .join(" ‹ ");
    if (where) {
      this.setState((current) => ({ detail: `${current.detail ?? ""}\n${where}`.slice(0, 500) }));
    }
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <View style={styles.container} accessibilityRole="alert">
          <UiStatePanel
            state="error"
            title="Qualcosa è andato storto"
            message="Si è verificato un errore imprevisto. Riavvia l'app o riprova più tardi."
            testID="app-error-boundary"
          />
          <Pressable
            accessibilityRole="button"
            onPress={() => this.setState({ hasError: false, detail: null })}
            style={styles.retry}
            testID="app-error-retry"
          >
            <Text style={styles.retryLabel}>Riprova</Text>
          </Pressable>
          {this.state.detail ? (
            <Text style={styles.detail} selectable testID="app-error-detail">
              {this.state.detail}
            </Text>
          ) : null}
        </View>
      );
    }

    return this.props.children;
  }
}

const styles = lazyStyles(() => StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    padding: theme.spacing.xl,
    backgroundColor: colors.background,
    gap: theme.spacing.md,
  },
  retry: {
    alignSelf: "center",
    minHeight: 44,
    paddingHorizontal: theme.spacing.lg,
    borderRadius: theme.radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    justifyContent: "center",
  },
  retryLabel: { color: colors.foreground, fontWeight: "700" },
  detail: { color: colors.foregroundMuted, fontSize: 11, textAlign: "center" },
}));
