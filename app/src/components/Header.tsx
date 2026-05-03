import { StyleSheet, View, Image, TouchableOpacity } from "react-native";
import VardHorizontalLogo from "../../assets/vard_logo_horizontal.svg";
import NotificationsIcon from "../../assets/notification_icon.svg";
import { SafeAreaView } from "react-native-safe-area-context";

type HeaderProps = {
  notificationFunction: Function;
};

export function Header({ notificationFunction }: HeaderProps) {
  return (
    <SafeAreaView edges={["top"]} style={{ backgroundColor: "#FFFFFF" }}>
      <View style={styles.container}>
        <View style={styles.left}>
          <Image
            source={require("../../assets/default_avatar.png")}
            style={styles.avatar}
          />
        </View>
        <View style={styles.center}>
          <VardHorizontalLogo width={128} height={32} />
        </View>
        <View style={styles.right}>
          <TouchableOpacity onPress={() => notificationFunction()}>
            <NotificationsIcon width={24} height={24} />
          </TouchableOpacity>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 18,
    paddingTop:8,
    paddingBottom: 24,
    backgroundColor: "#FFFFFF",
    borderBottomWidth: 1,
    borderBottomColor: "#caccd1",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },

  left: {
    width: 40,
    alignItems: "flex-start",
  },

  center: {
    position: "absolute",
    left: 0,
    right: 0,
    alignItems: "center",
  },

  right: {
    width: 40,
    alignItems: "flex-end",
  },

  avatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
  },

  iconPlaceholder: {
    width: 24,
    height: 24,
    backgroundColor: "#302611",
    borderRadius: 4,
  },
});
