import { AuthApp, resolveInitialAuthView } from "./auth/AuthApp";

export function App() {
  const initialView =
    typeof window !== "undefined"
      ? resolveInitialAuthView(window.location.search)
      : "login";

  return <AuthApp initialView={initialView} />;
}
