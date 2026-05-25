import { StyleSheet } from "react-native";

export const HOME_FONTS = {
  regular: "Poppins-Regular",
  medium: "Poppins-Medium",
  semiBold: "Poppins-SemiBold",
  bold: "Poppins-Bold",
  black: "Poppins-Black",
} as const;

export const REAL_TIME_TITLE_GRADIENT_ID = "realTimeMonitoringTitleGradient";
export const STATUS_CARD_GRADIENT_COLORS = ["#03CDF4", "#019BDE", "#01EBD0"] as const;
export const STATUS_CARD_GRADIENT_LOCATIONS = [0.08, 0.38, 1] as const;

export const styles = StyleSheet.create({
  content: {
    paddingTop: 30,
    paddingInline: 30,
  },
  section: {
    marginTop: 40,
  },
  sectionTitle: {
    color: "#000000",
    fontFamily: HOME_FONTS.bold,
    fontSize: 24,
    lineHeight: 30,
    textAlign: "left",
  },
  alertsContainer: {
    alignItems: "flex-start",
    backgroundColor: "transparent",
    marginTop: 24,
  },
  alertsCard: {
    backgroundColor: "#FFFFFF",
    borderColor: "#E7EBF0",
    borderRadius: 34,
    borderWidth: 2,
    minHeight: 228,
    overflow: "hidden",
    width: "100%",
  },
  alertRow: {
    alignItems: "center",
    flexDirection: "row",
    height: 76,
    paddingHorizontal: 20,
  },
  alertPlaceholderRow: {
    backgroundColor: "#F1F5F9",
    height: 76,
    width: "100%",
  },
  alertRowBorder: {
    borderBottomColor: "#E1E6EC",
    borderBottomWidth: 1.5,
  },
  alertIconWrap: {
    alignItems: "center",
    justifyContent: "center",
    marginRight: 14,
    width: 28,
  },
  alertTextWrap: {
    flex: 1,
    minWidth: 0,
  },
  noAlerts: {
    alignItems: "center",
    backgroundColor: "#F1F5F9",
    borderColor: "#D6DEE7",
    borderRadius: 22,
    borderStyle: "dashed",
    borderWidth: 1.5,
    minHeight: 228,
    justifyContent: "center",
    paddingHorizontal: 24,
    paddingVertical: 22,
    width: "100%",
  },
  noAlertsIcon: {
    alignSelf: "center",
    marginBottom: 10,
  },
  noAlertsText: {
    color: "#3F4852",
    fontFamily: HOME_FONTS.regular,
    fontSize: 18,
    lineHeight: 25,
    textAlign: "center",
  },
  alertButton: {
    backgroundColor: "#FFFFFF",
    borderColor: "#E7EEF5",
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 12,
    width: "100%",
  },
  alertButtonPressed: {
    backgroundColor: "rgba(1, 155, 222, 0.08)",
  },
  alertText: {
    color: "#404850",
    fontFamily: HOME_FONTS.regular,
    fontSize: 16,
    lineHeight: 24,
  },
  alertHeader: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 12,
  },
  alertTitle: {
    color: "#000000",
    fontFamily: HOME_FONTS.bold,
    fontSize: 20,
    lineHeight: 25,
  },
  alertWorkspace: {
    color: "#5F6368",
    fontFamily: HOME_FONTS.regular,
    fontSize: 14,
    lineHeight: 19,
  },
  alertSeverity: {
    fontFamily: HOME_FONTS.semiBold,
    fontSize: 12,
    lineHeight: 18,
  },
  alertSubtitle: {
    color: "#404850",
    fontFamily: HOME_FONTS.regular,
    fontSize: 13,
    lineHeight: 18,
    marginTop: 6,
  },
  alertDate: {
    color: "#8A94A3",
    fontFamily: HOME_FONTS.regular,
    fontSize: 12,
    lineHeight: 17,
    marginTop: 6,
  },
  realTimeMonitoringBorder: {
    marginTop: 26,
    borderRadius: 32,
    paddingLeft: 8,
    overflow: "hidden",
  },

  realTimeMonitoringContainer: {
    backgroundColor: "#FFFFFF",
    borderRadius: 32,
    overflow: "hidden",
    paddingBlock: 12,
    paddingInline: 8,
  },
  realTimeMonitoringHeader: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingTop: 16,
  },
  realTimeCheckIcon: {
    alignItems: "center",
    borderRadius: 999,
    height: 28,
    justifyContent: "center",
    width: 28,
  },
  realTimeMonitoringTitle: {
    marginLeft: 8,
  },
  realTimeMonitoringText: {
    color: "#171C1F",
    fontFamily: HOME_FONTS.medium,
    fontSize: 20,
    lineHeight: 24,
    paddingHorizontal: 16,
    paddingBottom: 16,
    paddingTop: 10,
  },
  emergencyButtonsContainer: {
    minHeight: 180,
    borderRadius: 32,
    padding: 32,
    flexDirection: "column",
    justifyContent: "center",
    alignItems: "center",
    overflow: "hidden",
  },
  emergencyButtonsEstateText: {
    color: "#FFFFFF",
    fontFamily: HOME_FONTS.semiBold,
    fontSize: 30,
    lineHeight: 32,
  },
  emergencyButtonsDescriptionText: {
    marginBlock: 12,
    color: "#FFFFFF",
    fontFamily: HOME_FONTS.regular,
    fontSize: 17,
    lineHeight: 20,
  },
  emergencyButton: {
    marginTop: 16,
    flexDirection: "row",
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 8,
    width: "100%",
  },
  emergencyButtonText: {
    padding: 12,
    fontFamily: HOME_FONTS.semiBold,
    fontSize: 18,
    color: "#03CDF4",
  },
});
