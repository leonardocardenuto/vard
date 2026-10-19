import { Image, Pressable, StyleSheet, View } from "react-native";
import VardHorizontalLogo from "../../assets/vard-logo.svg";
import { SafeAreaView } from "react-native-safe-area-context";

type HeaderProps = {
  avatarUrl?: string | null;
  profileFunction: () => void;
};

export function Header({ avatarUrl, profileFunction }: HeaderProps) {
  const avatarSource = avatarUrl?.trim()
    ? { uri: avatarUrl.trim() }
    : require("../../assets/default_avatar.png");

  return (
    <SafeAreaView edges={["top"]} style={styles.safeArea}>
      <View style={styles.container}>
        <Pressable
          accessibilityLabel="Abrir configurações do perfil"
          accessibilityRole="button"
          onPress={profileFunction}
          style={({ pressed }) => [styles.left, { opacity: pressed ? 0.65 : 1 }]}
          hitSlop={8}
        >
          <Image
            source={avatarSource}
            style={styles.avatar}
          />
        </Pressable>
        <View style={styles.center}>
          <VardHorizontalLogo height={22} />
        </View>
        <View style={styles.right} />
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

});
