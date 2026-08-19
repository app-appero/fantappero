import { BrowserRouter } from "./router/simpleRouter";
import { AuthProvider } from "./auth/AuthContext";
import { AppErrorBoundary } from "./errors/AppErrorBoundary";
import { AppRoutes } from "./routes";
import { ThemeProvider } from "./theme/ThemeProvider";

export function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <AppErrorBoundary>
            <AppRoutes />
          </AppErrorBoundary>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}
