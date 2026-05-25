import { StyleSheet } from "react-native";

export const ALERT_FONTS = {
  regular: "Poppins-Regular",
  medium: "Poppins-Medium",
  semiBold: "Poppins-SemiBold",
  bold: "Poppins-Bold",
  extraBold: "Poppins-ExtraBold",
  black: "Poppins-Black",
} as const;

export const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: "#F6FAFE",
  },
  content: {
    paddingHorizontal: 12,
    paddingTop: 18,
  },
  detailsContent: {
    paddingHorizontal: 17,
    paddingTop: 18,
  },
  headerRow: {
    alignItems: "center",
    flexDirection: "row",
    marginBottom: 28,
  },
  detailsHeaderRow: {
    alignItems: "center",
    flexDirection: "row",
    marginBottom: 22,
  },
  backButton: {
    alignItems: "center",
    height: 30,
    justifyContent: "center",
    marginRight: 8,
    width: 22,
  },
  title: {
    color: "#050505",
    flex: 1,
    fontFamily: ALERT_FONTS.semiBold,
    fontSize: 35,
    lineHeight: 42,
  },
  todayText: {
    color: "#171C1F",
    fontFamily: ALERT_FONTS.regular,
    fontSize: 11,
    marginTop: 8,
  },
  alertList: {
    gap: 12,
  },
  alertRow: {
    alignItems: "center",
    backgroundColor: "#FFFFFF",
    borderColor: "#C9CDD2",
    borderRadius: 10,
    borderWidth: 1,
    flexDirection: "row",
    minHeight: 65,
    paddingHorizontal: 14,
  },
  alertIconWrap: {
    alignItems: "center",
    justifyContent: "center",
    marginRight: 16,
    width: 18,
  },
  alertTextWrap: {
    flex: 1,
  },
  alertTitle: {
    color: "#171C1F",
    fontFamily: ALERT_FONTS.bold,
    fontSize: 17,
    lineHeight: 21,
  },
  alertMeta: {
    color: "#9A9A9A",
    fontFamily: ALERT_FONTS.regular,
    fontSize: 13,
    lineHeight: 18,
    marginTop: 1,
  },
  emptyText: {
    color: "#404850",
    fontFamily: ALERT_FONTS.regular,
    fontSize: 15,
    lineHeight: 22,
    marginTop: 10,
    textAlign: "center",
  },
  emptyState: {
    alignItems: "center",
    justifyContent: "center",
    minHeight: 450,
    paddingBottom: 80,
  },
  errorText: {
    color: "#B42318",
    fontFamily: ALERT_FONTS.regular,
    fontSize: 13,
    lineHeight: 19,
    marginBottom: 12,
  },
  detailsCard: {
    backgroundColor: "#FFFFFF",
    borderColor: "#D0D0D0",
    borderRadius: 14,
    borderWidth: 1,
    overflow: "hidden",
  },
  alertImage: {
    height: 168,
    width: "100%",
  },
  detailsBody: {
    paddingBottom: 22,
    paddingHorizontal: 12,
    paddingTop: 20,
  },
  detailsTitleRow: {
    alignItems: "center",
    flexDirection: "row",
    marginBottom: 12,
  },
  detailsTitle: {
    color: "#171C1F",
    fontFamily: ALERT_FONTS.bold,
    fontSize: 24,
    lineHeight: 30,
    marginLeft: 12,
  },
  bulletRow: {
    alignItems: "center",
    flexDirection: "row",
    marginBottom: 8,
    paddingLeft: 2,
  },
  bullet: {
    backgroundColor: "#171C1F",
    borderRadius: 999,
    height: 7,
    marginRight: 16,
    width: 7,
  },
  bulletText: {
    color: "#6D6D6D",
    fontFamily: ALERT_FONTS.regular,
    fontSize: 14,
    lineHeight: 20,
  },
  bulletTextStrong: {
    color: "#555555",
    fontFamily: ALERT_FONTS.bold,
  },
  emergencyButton: {
    alignItems: "center",
    borderRadius: 9,
    flexDirection: "row",
    height: 52,
    justifyContent: "center",
    marginTop: 14,
  },
  emergencyButtonPrimary: {
    backgroundColor: "#CA171B",
  },
  emergencyButtonOutline: {
    backgroundColor: "#FFFFFF",
    borderColor: "#CA171B",
    borderWidth: 1,
  },
  emergencyButtonText: {
    fontFamily: ALERT_FONTS.bold,
    fontSize: 16,
    marginLeft: 14,
  },
  emergencyButtonTextPrimary: {
    color: "#FFFFFF",
  },
  emergencyButtonTextOutline: {
    color: "#CA171B",
  },
  validationTitle: {
    color: "#050505",
    fontFamily: ALERT_FONTS.semiBold,
    fontSize: 16,
    lineHeight: 22,
    marginTop: 34,
    textTransform: "uppercase",
  },
  validationRow: {
    flexDirection: "row",
    gap: 24,
    marginTop: 12,
  },
  validationButton: {
    alignItems: "center",
    borderRadius: 9,
    flex: 1,
    height: 46,
    justifyContent: "center",
  },
  validationYes: {
    backgroundColor: "#151515",
  },
  validationNo: {
    backgroundColor: "#FFFFFF",
    borderColor: "#151515",
    borderWidth: 1,
  },
  validationText: {
    fontFamily: ALERT_FONTS.bold,
    fontSize: 15,
  },
  validationTextYes: {
    color: "#FFFFFF",
  },
  validationTextNo: {
    color: "#151515",
  },
  pressed: {
    opacity: 0.72,
  },
});
