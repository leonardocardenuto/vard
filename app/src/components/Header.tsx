import { Image, Pressable, StyleSheet, View } from "react-native";
import VardHorizontalLogo from "../../assets/vard-logo.svg";
import NotificationsIcon from "../../assets/notification_icon.svg";
import { SafeAreaView } from "react-native-safe-area-context";

type HeaderProps = {
  avatarUrl?: string | null;
  notificationFunction: Function;
};

export function Header({ avatarUrl, notificationFunction }: HeaderProps) {
  const avatarSource = avatarUrl?.trim()
    ? { uri: avatarUrl.trim() }
    : require("../../assets/default_avatar.png");

  return (
    <SafeAreaView edges={["top"]} style={styles.safeArea}>
      <View style={styles.container}>
        <View style={styles.left}>
          <Image
            source={avatarSource}
            style={styles.avatar}
          />
        </View>
        <View style={styles.center}>
          <VardHorizontalLogo height={22} />
        </View>
        <View style={styles.right}>
          <Pressable
            accessibilityLabel="Abrir alertas"
            accessibilityRole="button"
            onPress={() => notificationFunction()}
            style={styles.notificationButton}
          >
            <NotificationsIcon width={24} height={24} />
          </Pressable>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    backgroundColor: "#FFFFFF",
  },
  container: {
    alignItems: "center",
    backgroundColor: "#FFFFFF",
    borderBottomColor: "#caccd1",
    borderBottomWidth: 1,
    flexDirection: "row",
    height: 72,
    justifyContent: "space-between",
    paddingHorizontal: 18,
  },

  left: {
    alignItems: "flex-start",
    justifyContent: "center",
    width: 48,
  },

  center: {
    alignItems: "center",
    flex: 1,
    justifyContent: "center",
  },

  right: {
    alignItems: "flex-end",
    justifyContent: "center",
    width: 48,
  },

  avatar: {
    borderRadius: 20,
    height: 40,
    width: 40,
  },

  notificationButton: {
    alignItems: "center",
    height: 40,
    justifyContent: "center",
    width: 40,
  },
});
