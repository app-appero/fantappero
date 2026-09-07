import { ToastProvider } from "@fantappero/ui";
import { BrowserRouter } from "./router/simpleRouter";
import { ListoneRefreshProvider } from "./admin/ListoneRefreshContext";
import { AuthProvider } from "./auth/AuthContext";
import { AppErrorBoundary } from "./errors/AppErrorBoundary";
import { AppRoutes } from "./routes";
import { ThemeProvider } from "./theme/ThemeProvider";

export function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <ToastProvider>
          <AuthProvider>
            <ListoneRefreshProvider>
              <AppErrorBoundary>
                <AppRoutes />
              </AppErrorBoundary>
            </ListoneRefreshProvider>
          </AuthProvider>
        </ToastProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}
