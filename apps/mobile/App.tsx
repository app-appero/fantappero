import { StatusBar } from "expo-status-bar";
import { AuthScreen } from "./src/auth/AuthScreen";

export default function App() {
  return (
    <>
      <StatusBar style="light" />
      <AuthScreen />
    </>
  );
}
