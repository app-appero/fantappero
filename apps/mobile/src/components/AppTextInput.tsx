import { theme } from "@fantappero/ui/theme";
import { forwardRef } from "react";
import { TextInput, type TextInputProps } from "react-native";
import { useAppTheme } from "../theme/AppTheme";

const { colors } = theme;

/** TextInput whose placeholder follows the active theme (white on the dark theme). */
export const AppTextInput = forwardRef<TextInput, TextInputProps>(function AppTextInput(props, ref) {
  useAppTheme();
  return <TextInput {...props} ref={ref} placeholderTextColor={colors.inputPlaceholder} />;
});
