import { DefaultTheme as NavigationDefaultTheme } from '@react-navigation/native';
import { MD3LightTheme } from 'react-native-paper';

export const VARD_COLORS = {
  primary: "#00B9BB",
  primaryPressed: "#009B9D",
  primarySoft: "#DDF7F6",
  secondary: "#006496",
  secondarySoft: "#E6ECF6",
  surface: "#FFFFFF",
  background: "#F6FAFE",
  text: "#171C1F",
  muted: "#667085",
  border: "#D8E6F1",
  onBrand: "#FFFFFF",
} as const;

export const VARD_GRADIENT = [VARD_COLORS.primary, VARD_COLORS.secondary] as const;

export const VARD_PAPER_THEME = {
  ...MD3LightTheme,
  colors: {
    ...MD3LightTheme.colors,
    primary: VARD_COLORS.primary,
    onPrimary: VARD_COLORS.onBrand,
    primaryContainer: VARD_COLORS.primarySoft,
    onPrimaryContainer: VARD_COLORS.secondary,
    secondary: VARD_COLORS.secondary,
    onSecondary: VARD_COLORS.onBrand,
    secondaryContainer: VARD_COLORS.secondarySoft,
    onSecondaryContainer: VARD_COLORS.secondary,
    surface: VARD_COLORS.surface,
    background: VARD_COLORS.background,
    outline: VARD_COLORS.border,
  },
};

export const VARD_NAVIGATION_THEME = {
  ...NavigationDefaultTheme,
  colors: {
    ...NavigationDefaultTheme.colors,
    primary: VARD_COLORS.primary,
    background: VARD_COLORS.background,
    card: VARD_COLORS.surface,
    text: VARD_COLORS.text,
    border: VARD_COLORS.border,
    notification: VARD_COLORS.secondary,
  },
};
