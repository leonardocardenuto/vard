import {
  Feather,
  FontAwesome5,
  FontAwesome6,
  Ionicons,
} from "@expo/vector-icons";
import {
  RouteProp,
  useFocusEffect,
  useNavigation,
  useRoute,
} from "@react-navigation/native";
import {
  createNativeStackNavigator,
  NativeStackScreenProps,
} from "@react-navigation/native-stack";
import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Image,
  Linking,
  Pressable,
  ScrollView,
  Text,
  View,
} from "react-native";

import { LayoutWithNavbar } from "../../../components/LayoutWithNavbar";
import {
  ApiRequestError,
  NotificationResponse,
  getNotification,
  listNotifications,
  listWorkspaces,
  updateNotification,
} from "../../../lib/api";
import { AppTabParamList } from "../../../navigation/types";
import { styles } from "../styles/alerts";
import { AlertItem, AlertsStackParamList } from "../types";

type AlertsRoute = RouteProp<AppTabParamList, "Alerts">;
type AlertsListProps = NativeStackScreenProps<
  AlertsStackParamList,
  "AlertsList"
>;
type AlertDetailsProps = NativeStackScreenProps<
  AlertsStackParamList,
  "AlertDetails"
>;

const Stack = createNativeStackNavigator<AlertsStackParamList>();
const DEFAULT_ALERT_IMAGE_URL =
  "https://images.unsplash.com/photo-1581578731548-c64695cc6952?auto=format&fit=crop&w=900&q=80";

const EMERGENCY_PHONE_BY_LABEL: Record<string, string> = {
  "Bombeiro (193)": "193",
  "Policia (190)": "190",
  "SAMU (192)": "192",
};

export function Alerts() {
  const route = useRoute<AlertsRoute>();
  const accessToken = route.params?.accessToken ?? "";

  return (
    <Stack.Navigator
      screenOptions={{ headerShown: false, animation: "slide_from_right" }}
    >
      <Stack.Screen
        name="AlertsList"
        component={AlertsListScreen}
        initialParams={{ accessToken }}
      />
      <Stack.Screen name="AlertDetails" component={AlertDetailsScreen} />
    </Stack.Navigator>
  );
}

function AlertsListScreen({ navigation, route }: AlertsListProps) {
  const tabNavigation = useNavigation();
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const accessToken = route.params.accessToken;

  const loadAlerts = useCallback(async () => {
    if (!accessToken) {
      setAlerts([]);
      setIsLoading(false);
      return;
    }

    try {
      setErrorMessage("");
      setIsLoading(true);
      const workspaces = await listWorkspaces(accessToken);
      const notificationsByWorkspace = await Promise.all(
        workspaces.map((workspace) =>
          listNotifications(accessToken, workspace.id),
        ),
      );
      setAlerts(notificationsByWorkspace.flat().map(notificationToAlert));
    } catch (error) {
      setErrorMessage(
        error instanceof ApiRequestError
          ? error.message
          : "Nao foi possivel carregar os alertas.",
      );
      setAlerts([]);
    } finally {
      setIsLoading(false);
    }
  }, [accessToken]);

  useFocusEffect(
    useCallback(() => {
      void loadAlerts();
    }, [loadAlerts]),
  );

  return (
    <LayoutWithNavbar>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.headerRow}>
          <Pressable
            onPress={() => tabNavigation.navigate("Home" as never)}
            style={styles.backButton}
          >
            <Feather color="#050505" name="chevron-left" size={27} />
          </Pressable>
          <Text style={styles.title}>Alertas</Text>
          <Text style={styles.todayText}>Hoje</Text>
        </View>

        {isLoading ? <ActivityIndicator color="#019BDE" /> : null}
        {errorMessage ? (
          <Text style={styles.errorText}>{errorMessage}</Text>
        ) : null}

        {!isLoading && alerts.length === 0 ? (
          <View style={styles.emptyState}>
            <Feather color="#A8AFB6" name="check-circle" size={31} />
            <Text style={styles.emptyText}>
              Nenhum incidente{"\n"}detectado hoje.
            </Text>
          </View>
        ) : null}

        <View style={styles.alertList}>
          {alerts.map((alert) => (
            <Pressable
              accessibilityRole="button"
              key={alert.id}
              onPress={() =>
                navigation.navigate("AlertDetails", {
                  accessToken,
                  alert,
                  openedFrom: "alerts",
                })
              }
              style={({ pressed }) => [
                styles.alertRow,
                pressed && styles.pressed,
              ]}
            >
              <View style={styles.alertIconWrap}>
                {renderAlertIcon(alert.kind, 24)}
              </View>
              <View style={styles.alertTextWrap}>
                <Text style={styles.alertTitle}>{alert.title}</Text>
                <Text numberOfLines={1} style={styles.alertMeta}>
                  {"\u2022"} {alert.room} - Horario: {alert.time}
                </Text>
              </View>
              <Feather color="#757B80" name="chevron-right" size={25} />
            </Pressable>
          ))}
        </View>
      </ScrollView>
    </LayoutWithNavbar>
  );
}

function AlertDetailsScreen({ navigation, route }: AlertDetailsProps) {
  const { accessToken, alert, openedFrom } = route.params;
  const [isValidationAnswered, setIsValidationAnswered] = useState(
    alert.isValidationAnswered,
  );
  const title = alert.kind === "fall" ? "Fall Detected" : alert.title;

  useFocusEffect(
    useCallback(() => {
      async function syncAlertValidation() {
        try {
          const notification = await getNotification(accessToken, alert.id);
          const isAnswered = hasDetectionValidation(notification.payload);
          setIsValidationAnswered(isAnswered);
          navigation.setParams({
            alert: {
              ...alert,
              isValidationAnswered: isAnswered,
              payload: notification.payload,
            },
          });
        } catch {
          setIsValidationAnswered(alert.isValidationAnswered);
        }
      }

      void syncAlertValidation();
    }, [accessToken, alert.id, navigation]),
  );

  async function handleValidate(isValid: boolean) {
    setIsValidationAnswered(true);

    try {
      const updatedNotification = await updateNotification(accessToken, alert.id, {
        payload: {
          ...alert.payload,
          detection_validation: {
            answered_at: new Date().toISOString(),
            is_valid: isValid,
          },
        },
      });
      navigation.setParams({
        alert: {
          ...alert,
          isValidationAnswered: true,
          payload: updatedNotification.payload,
        },
      });
    } catch {
      setIsValidationAnswered(false);
    }
  }

  return (
    <LayoutWithNavbar>
      <ScrollView
        contentContainerStyle={styles.detailsContent}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.detailsHeaderRow}>
          <Pressable
            onPress={() => {
              if (openedFrom === "home") {
                navigation.getParent()?.navigate("Home");
                return;
              }

              navigation.goBack();
            }}
            style={styles.backButton}
          >
            <Feather color="#050505" name="chevron-left" size={27} />
          </Pressable>
          <Text style={styles.title}>Alertas</Text>
        </View>

        <View style={styles.detailsCard}>
          {alert.imageUrl ? (
            <Image source={{ uri: alert.imageUrl }} style={styles.alertImage} />
          ) : null}
          <View style={styles.detailsBody}>
            <View style={styles.detailsTitleRow}>
              {renderAlertIcon(alert.kind, 29)}
              <Text style={styles.detailsTitle}>{title}</Text>
            </View>

            <Bullet label="Local" value={alert.room} />
            <Bullet label="Horario" value={alert.time} />
            <Bullet label="Nivel de precisao" value={`${alert.precision}%`} />

            <EmergencyButton label="SAMU (192)" primary />
            <EmergencyButton label="Policia (190)" />
            <EmergencyButton label="Bombeiro (193)" />
          </View>
        </View>

        {!isValidationAnswered ? (
          <>
            <Text style={styles.validationTitle}>A deteccao e valida?</Text>
            <View style={styles.validationRow}>
              <Pressable
                onPress={() => void handleValidate(true)}
                style={({ pressed }) => [
                  styles.validationButton,
                  styles.validationYes,
                  pressed && styles.pressed,
                ]}
              >
                <Text style={[styles.validationText, styles.validationTextYes]}>
                  SIM
                </Text>
              </Pressable>
              <Pressable
                onPress={() => void handleValidate(false)}
                style={({ pressed }) => [
                  styles.validationButton,
                  styles.validationNo,
                  pressed && styles.pressed,
                ]}
              >
                <Text style={[styles.validationText, styles.validationTextNo]}>
                  NAO
                </Text>
              </Pressable>
            </View>
          </>
        ) : null}
      </ScrollView>
    </LayoutWithNavbar>
  );
}

function Bullet({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.bulletRow}>
      <View style={styles.bullet} />
      <Text style={styles.bulletText}>
        <Text style={styles.bulletTextStrong}>{label}: </Text>
        {value}
      </Text>
    </View>
  );
}

function EmergencyButton({
  label,
  primary = false,
}: {
  label: string;
  primary?: boolean;
}) {
  return (
    <Pressable
      onPress={() => {
        const phoneNumber = EMERGENCY_PHONE_BY_LABEL[label];
        if (phoneNumber) {
          Linking.openURL(`tel:${phoneNumber}`);
        }
      }}
      style={({ pressed }) => [
        styles.emergencyButton,
        primary ? styles.emergencyButtonPrimary : styles.emergencyButtonOutline,
        pressed && styles.pressed,
      ]}
    >
      <FontAwesome5
        color={primary ? "#FFFFFF" : "#CA171B"}
        name="asterisk"
        size={17}
      />
      <Text
        style={[
          styles.emergencyButtonText,
          primary
            ? styles.emergencyButtonTextPrimary
            : styles.emergencyButtonTextOutline,
        ]}
      >
        {label}
      </Text>
    </Pressable>
  );
}

function renderAlertIcon(kind: AlertItem["kind"], size: number) {
  if (kind === "fall") {
    return <FontAwesome6 color="#CA171B" name="person-falling" size={size} />;
  }

  if (kind === "fight") {
    return <Ionicons color="#007D88" name="alert-circle-outline" size={size} />;
  }

  return <Ionicons color="#019BDE" name="notifications-outline" size={size} />;
}

function notificationToAlert(notification: NotificationResponse): AlertItem {
  const payload = notification.payload ?? {};
  const rawTitle =
    notification.title || notification.notification_type || "Alert";
  const normalizedTitle = rawTitle.toLowerCase();
  const kind = normalizedTitle.includes("fall")
    ? "fall"
    : normalizedTitle.includes("fight")
      ? "fight"
      : "general";

  return {
    id: notification.id,
    title: kind === "fall" ? "Fall" : kind === "fight" ? "Fight" : rawTitle,
    kind,
    room:
      stringFromPayload(payload, ["room", "location", "camera_name"]) ??
      "Local nao informado",
    time: formatAlertTime(notification.created_at),
    precision:
      numberFromPayload(payload, ["precision", "confidence", "accuracy"]) ?? 0,
    imageUrl:
      stringFromPayload(payload, ["image_url", "snapshot_url", "photo_url"]) ??
      DEFAULT_ALERT_IMAGE_URL,
    isValidationAnswered: hasDetectionValidation(payload),
    payload,
  };
}

function hasDetectionValidation(payload: Record<string, unknown>) {
  const validation = payload.detection_validation;

  if (!validation || typeof validation !== "object") {
    return false;
  }

  const validationPayload = validation as Record<string, unknown>;

  return (
    typeof validationPayload.is_valid === "boolean" ||
    typeof validationPayload.answered_at === "string"
  );
}

function stringFromPayload(payload: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = payload[key];
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  return null;
}

function numberFromPayload(payload: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = payload[key];
    if (typeof value === "number") {
      return Math.round(value);
    }
    if (
      typeof value === "string" &&
      value.trim() &&
      !Number.isNaN(Number(value))
    ) {
      return Math.round(Number(value));
    }
  }
  return null;
}

function formatAlertTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "--:--:--";
  }

  return date.toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}
