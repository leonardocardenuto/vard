import { StyleSheet } from "react-native";

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#f5f7fa",
    paddingTop: 50,
    paddingHorizontal: 20,
  },

  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },

  avatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
  },

  logo: {
    fontSize: 20,
    fontWeight: "bold",
    color: "#00a8cc",
  },

  title: {
    fontSize: 24,
    fontWeight: "bold",
    marginTop: 20,
  },

  subtitle: {
    color: "#777",
    marginBottom: 15,
  },

  alertCard: {
    backgroundColor: "#fdecea",
    borderRadius: 15,
    padding: 15,
    borderWidth: 1,
    borderColor: "#e74c3c",
    marginBottom: 20,
  },

  alertHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 10,
  },

  alertTitle: {
    fontWeight: "bold",
    color: "#c0392b",
  },

  alertSubtitle: {
    color: "#555",
  },

  secondaryButton: {
    backgroundColor: "#fff",
    padding: 12,
    borderRadius: 10,
    marginVertical: 5,
  },

  secondaryText: {
    textAlign: "center",
    color: "#c0392b",
    fontWeight: "bold",
  },

  primaryButton: {
    backgroundColor: "#e74c3c",
    padding: 12,
    borderRadius: 10,
  },

  primaryText: {
    textAlign: "center",
    color: "#fff",
    fontWeight: "bold",
  },

  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 10,
  },

  sectionTitle: {
    fontWeight: "bold",
    fontSize: 16,
  },

  live: {
    color: "#00a8cc",
    fontSize: 12,
  },

  activityCard: {
    backgroundColor: "#fff",
    padding: 15,
    borderRadius: 12,
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 10,
  },

  snapshotCard: {
    backgroundColor: "#fff",
    padding: 15,
    borderRadius: 12,
    marginBottom: 20,
  },

  snapshotHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 10,
  },

  imageRow: {
    flexDirection: "row",
    justifyContent: "space-between",
  },

  snapshotImage: {
    width: "48%",
    height: 100,
    borderRadius: 10,
  },

  caregivers: {
    flexDirection: "row",
    marginBottom: 80,
  },

  person: {
    alignItems: "center",
    marginRight: 15,
  },

  personImage: {
    width: 50,
    height: 50,
    borderRadius: 25,
    marginBottom: 5,
  },

  addPerson: {
    width: 50,
    height: 50,
    borderRadius: 25,
    borderWidth: 1,
    borderStyle: "dashed",
    justifyContent: "center",
    alignItems: "center",
  },

  bottomNav: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    height: 70,
    backgroundColor: "#fff",
    flexDirection: "row",
    justifyContent: "space-around",
    alignItems: "center",
  },

  activeTab: {
    backgroundColor: "#00a8cc",
    padding: 12,
    borderRadius: 20,
  },

  activityText: {
    fontWeight: "500",
  },

  time: {
    fontSize: 12,
    color: "#777",
  },
});

export { styles };