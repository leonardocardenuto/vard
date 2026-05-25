import { StyleSheet } from 'react-native';

const WORKSPACES_FONTS = {
  regular: "Poppins-Regular",
  medium: "Poppins-Medium",
  semiBold: "Poppins-SemiBold",
  bold: "Poppins-Bold",
  extraBold: "Poppins-ExtraBold",
} as const;

const WORKSPACE_GRADIENT_COLORS = ['#03CDF4', '#019BDE', '#01EBD0'] as const;
const WORKSPACE_GRADIENT_LOCATIONS = [0.08, 0.48, 1] as const;

const styles = StyleSheet.create({
  flex: {
    flex: 1,
  },
  content: {
    paddingHorizontal: 26,
    paddingTop: 28,
    paddingBottom: 144,
  },
  title: {
    flexShrink: 1,
    height: 42,
    width: 136,
  },
  hero: {
    alignItems: "flex-start",
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 18,
    marginBottom: 20,
  },
  titleSvg: {
    height: 38,
    width: 190,
  },
  titleSmall: {
    color: "#101828",
    fontFamily: WORKSPACES_FONTS.extraBold,
    fontSize: 25,
    lineHeight: 31,
  },
  subtitle: {
    color: "#4B5563",
    fontFamily: WORKSPACES_FONTS.regular,
    fontSize: 16,
    lineHeight: 21,
    marginTop: 0,
  },
  addButton: {
    alignItems: "center",
    height: 44,
    justifyContent: "center",
    marginTop: 2,
    width: 44,
  },
  pressed: {
    opacity: 0.72,
  },
  centerState: {
    alignItems: "center",
    paddingTop: 42,
    gap: 10,
  },
  centerStateText: {
    color: "#667085",
    fontFamily: WORKSPACES_FONTS.regular,
    fontSize: 14,
  },
  errorText: {
    color: "#B42318",
    fontFamily: WORKSPACES_FONTS.bold,
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 14,
  },
  emptyCard: {
    alignItems: "center",
    backgroundColor: "#FFFFFF",
    borderColor: "#E7EEF5",
    borderRadius: 20,
    borderWidth: 1,
    padding: 22,
  },
  emptyTitle: {
    color: "#101828",
    fontFamily: WORKSPACES_FONTS.bold,
    fontSize: 17,
    marginTop: 10,
  },
  emptyText: {
    color: "#667085",
    fontFamily: WORKSPACES_FONTS.regular,
    fontSize: 14,
    lineHeight: 20,
    marginTop: 6,
    textAlign: "center",
  },
  workspaceCardGradient: {
    borderRadius: 13,
    marginBottom: 24,
    padding: 1,
  },
  workspaceCard: {
    marginBottom: 24,
    backgroundColor: "#FFFFFF",
    borderRadius: 12,
    minHeight: 124,
    overflow: "hidden",
    borderColor: "#585858",
    borderWidth: 1,
  },
  workspaceImageWrap: {
    height: 182,
    position: "relative",
    width: "100%",
  },
  workspaceImage: {
    height: "100%",
    width: "100%",
  },
  workspaceMenuButton: {
    alignItems: "center",
    backgroundColor: "#FFFFFF",
    borderRadius: 999,
    height: 24,
    justifyContent: "center",
    position: "absolute",
    right: 10,
    top: 10,
    width: 24,
  },
  workspaceCardFooter: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
    minHeight: 60,
    paddingHorizontal: 22,
  },
  workspaceName: {
    color: "#101828",
    flex: 1,
    fontFamily: WORKSPACES_FONTS.bold,
    fontSize: 20,
    lineHeight: 26,
    paddingRight: 14,
  },
  formHeader: {
    flexDirection: "row",
    gap: 12,
    marginBottom: 22,
  },
  backButton: {
    alignItems: "center",
    height: 34,
    justifyContent: "center",
    width: 34,
  },
  formHeaderText: {
    flex: 1,
  },
  formCard: {
    backgroundColor: "#FFFFFF",
    borderColor: "#E7EEF5",
    borderRadius: 20,
    borderWidth: 1,
    padding: 16,
    marginBottom: 14,
  },
  inputLabel: {
    color: "#101828",
    fontFamily: WORKSPACES_FONTS.bold,
    fontSize: 13,
    marginBottom: 8,
  },
  input: {
    backgroundColor: "#F8FAFC",
    borderColor: "#E5E7EB",
    borderRadius: 14,
    borderWidth: 1,
    color: "#111827",
    fontFamily: WORKSPACES_FONTS.regular,
    fontSize: 14,
    marginBottom: 14,
    minHeight: 50,
    paddingHorizontal: 14,
  },
  slugPreview: {
    backgroundColor: "#F0F9FF",
    borderRadius: 14,
    padding: 12,
  },
  slugLabel: {
    color: "#667085",
    fontFamily: WORKSPACES_FONTS.bold,
    fontSize: 12,
  },
  slugValue: {
    color: "#019BDE",
    fontFamily: WORKSPACES_FONTS.bold,
    fontSize: 14,
    marginTop: 4,
  },
  primaryButton: {
    borderRadius: 16,
    minHeight: 54,
    overflow: "hidden",
  },
  primaryButtonGradient: {
    alignItems: "center",
    flex: 1,
    justifyContent: "center",
    minHeight: 54,
  },
  primaryButtonText: {
    color: "#FFFFFF",
    fontFamily: WORKSPACES_FONTS.extraBold,
    fontSize: 16,
  },
});

export {
  WORKSPACE_GRADIENT_COLORS,
  WORKSPACE_GRADIENT_LOCATIONS,
  WORKSPACES_FONTS,
  styles,
};
