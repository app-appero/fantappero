import { ToastProvider } from "@fantappero/ui";
import { BrowserRouter } from "./router/simpleRouter";
import { ListoneRefreshProvider } from "./admin/ListoneRefreshContext";
import { AthleteCardProvider } from "./athletes/AthleteCard";
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
            <AthleteCardProvider>
            <ListoneRefreshProvider>
              <AppErrorBoundary>
                <AppRoutes />
              </AppErrorBoundary>
            </ListoneRefreshProvider>
            </AthleteCardProvider>
          </AuthProvider>
        </ToastProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}
