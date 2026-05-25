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
    marginTop: 16,
    backgroundColor: "transparent",
    alignItems: "flex-start",
    gap: 10,
  },
  noAlerts: {
    padding: 24,
    width: "100%",
    alignItems: "center",
  },
  noAlertsIcon: {
    alignSelf: "center",
    marginBottom: 8,
  },
  noAlertsText: {
    color: "#404850",
    fontFamily: HOME_FONTS.regular,
    fontSize: 16,
    lineHeight: 22,
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
  realTimeMonitoringBorder: {
    marginTop: 16,
    borderRadius: 32,
    paddingLeft: 8,
    overflow: "hidden",
  },

  realTimeMonitoringContainer: {
    backgroundColor: "#FFFFFF",
    borderRadius: 32,
    overflow: "hidden",
  },
  realTimeMonitoringHeader: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingTop: 16,
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
