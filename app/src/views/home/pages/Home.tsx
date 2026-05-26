import { RouteProp, useFocusEffect, useRoute } from "@react-navigation/native";
import { Feather, FontAwesome6 } from "@expo/vector-icons";
import { BottomTabNavigationProp } from "@react-navigation/bottom-tabs";
import { useNavigation } from "@react-navigation/native";
import { LinearGradient as ExpoLinearGradient } from "expo-linear-gradient";
import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Linking,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import Svg, {
  Defs,
  LinearGradient,
  Stop,
  Text as SvgText,
} from "react-native-svg";
import { LayoutWithNavbar } from "../../../components/LayoutWithNavbar";
import {
  ApiRequestError,
  NotificationResponse,
  listNotifications,
  listWorkspaces,
} from "../../../lib/api";
import { AppTabParamList } from "../../../navigation/types";
import { AlertItem } from "../../alerts/types";
import {
  HOME_FONTS,
  styles,
} from "../styles/Home";

import AmbulanceIcon from "../../../../assets/ambulance_icon.svg";
import FirefighterIcon from "../../../../assets/firefighters_icon.svg";
import NoIncidentsIcon from "../../../../assets/no_incident_icon.svg";
import PoliceIcon from "../../../../assets/police_icon.svg";

type HomeRoute = RouteProp<AppTabParamList, "Home">;
type HomeNavigation = BottomTabNavigationProp<AppTabParamList, "Home">;

type HomeAlert = NotificationResponse & {
  workspaceName: string;
};

const REAL_TIME_TITLE_GRADIENT_ID = "realTimeMonitoringTitleGradient";
const STATUS_CARD_GRADIENT_COLORS = ["#03CDF4", "#019BDE", "#01EBD0"] as const;
const STATUS_CARD_GRADIENT_LOCATIONS = [0.08, 0.38, 1] as const;

const openDialer = (phoneNumber: string) => {
  Linking.openURL(`tel:${phoneNumber}`);
};

export function Home() {
  const route = useRoute<HomeRoute>();
  const navigation = useNavigation<HomeNavigation>();
  const accessToken = route.params?.accessToken ?? "";
  const [alerts, setAlerts] = useState<HomeAlert[]>([]);
  const [isLoadingAlerts, setIsLoadingAlerts] = useState(true);
  const [isRefreshingAlerts, setIsRefreshingAlerts] = useState(false);
  const [alertsError, setAlertsError] = useState("");
  const hasAlerts = alerts.length > 0;
  const visibleAlerts = alerts.slice(0, 3);
  const emptyAlertRows = Math.max(0, 3 - visibleAlerts.length);

  const loadAlerts = useCallback(async () => {
    if (!accessToken) {
      setAlerts([]);
      setAlertsError("Sessao invalida. Faca login novamente.");
      setIsLoadingAlerts(false);
      return;
    }

    try {
      setAlertsError("");
      setIsLoadingAlerts(true);
      const workspaces = await listWorkspaces(accessToken);
      if (workspaces.length === 0) {
        setAlerts([]);
        return;
      }

      const workspaceNotifications = await Promise.all(
        workspaces.map(async (workspace) =>
          (await listNotifications(accessToken, workspace.id)).map((notification) => ({
            ...notification,
            workspaceName: workspace.name,
          })),
        ),
      );
      const today = new Date();

      const notifications = workspaceNotifications
        .flat()
        .filter((notification) => {
          const createdAt = new Date(notification.created_at);

          return (
            createdAt.getDate() === today.getDate() &&
            createdAt.getMonth() === today.getMonth() &&
            createdAt.getFullYear() === today.getFullYear()
          );
        })
        .sort((first, second) => {
          return (
            new Date(second.created_at).getTime() -
            new Date(first.created_at).getTime()
          );
        });

      setAlerts(notifications);
    } catch (error) {
      setAlerts([]);
      setAlertsError(
        error instanceof ApiRequestError
          ? error.message
          : "Nao foi possivel carregar os alertas.",
      );
    } finally {
      setIsLoadingAlerts(false);
    }
  }, [accessToken]);

  useFocusEffect(
    useCallback(() => {
      void loadAlerts();
    }, [loadAlerts]),
  );

  const handleRefresh = useCallback(async () => {
    setIsRefreshingAlerts(true);
    try {
      await loadAlerts();
    } finally {
      setIsRefreshingAlerts(false);
    }
  }, [loadAlerts]);

  return (
    <LayoutWithNavbar>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            colors={["#019BDE"]}
            onRefresh={handleRefresh}
            refreshing={isRefreshingAlerts}
            tintColor="#019BDE"
          />
        }
        showsVerticalScrollIndicator={false}
      >
        <View>
          <Text style={styles.sectionTitle}>Últimos Alertas</Text>
          <View style={styles.alertsContainer}>
            {hasAlerts ? (
              <View style={styles.alertsCard}>
                {visibleAlerts.map((alert, index) => (
                  <Pressable
                    accessibilityLabel={`Abrir ${getAlertTitle(alert)}`}
                    accessibilityRole="button"
                    key={alert.id}
                    onPress={() =>
                      navigation.navigate(
                        "Alerts",
                        {
                          accessToken,
                          params: {
                            accessToken,
                            alert: notificationToAlert(alert),
                            openedFrom: "home",
                          },
                          screen: "AlertDetails",
                          userAvatarUrl: route.params?.userAvatarUrl,
                          userEmail: route.params?.userEmail ?? "",
                          userName: route.params?.userName,
                        },
                      )
                    }
                    style={({ pressed }) => [
                      styles.alertRow,
                      index < 2 && styles.alertRowBorder,
                      pressed && styles.alertButtonPressed,
                    ]}
                  >
                    <View style={styles.alertIconWrap}>
                      {renderAlertIcon(alert)}
                    </View>
                    <View style={styles.alertTextWrap}>
                      <Text style={styles.alertTitle}>
                        {getAlertTitle(alert)}
                      </Text>
                      <Text style={styles.alertWorkspace}>
                        {formatWorkspaceName(alert.workspaceName)}
                      </Text>
                    </View>
                    <Feather color="#737B84" name="chevron-right" size={26} />
                  </Pressable>
                ))}
                {Array.from({ length: emptyAlertRows }).map((_, index) => (
                  <View
                    key={`empty-alert-row-${index}`}
                    style={[
                      styles.alertPlaceholderRow,
                      visibleAlerts.length + index < 2 && styles.alertRowBorder,
                    ]}
                  />
                ))}
              </View>
            ) : (
              <View
                accessibilityLabel="Nenhum incidente detectado hoje"
                accessibilityRole="summary"
                style={styles.noAlerts}
              >
                <NoIncidentsIcon
                  height={40}
                  style={styles.noAlertsIcon}
                  width={40}
                />
                <Text style={styles.noAlertsText}>
                  Nenhum incidente{"\n"}detectado hoje.
                </Text>
              </View>
            )}
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Monitoramento</Text>
          <ExpoLinearGradient
            colors={["#03CDF4", "#019BDE", "#01EBD0"]}
            locations={[0.08, 0.38, 1]}
            start={{ x: 0, y: 0 }}
            end={{ x: 0, y: 1 }}
            style={styles.realTimeMonitoringBorder}
          >
            <View style={styles.realTimeMonitoringContainer}>
              <View style={styles.realTimeMonitoringHeader}>
                <ExpoLinearGradient
                  colors={STATUS_CARD_GRADIENT_COLORS}
                  locations={STATUS_CARD_GRADIENT_LOCATIONS}
                  start={{ x: 0, y: 0 }}
                  end={{ x: 1, y: 1 }}
                  style={styles.realTimeCheckIcon}
                >
                  <Feather color="#FFFFFF" name="check" size={18} />
                </ExpoLinearGradient>
                <View style={styles.realTimeMonitoringTitle}>
                  <Svg height={24} width={155}>
                    <Defs>
                      <LinearGradient
                        id={REAL_TIME_TITLE_GRADIENT_ID}
                        x1="0%"
                        x2="100%"
                        y1="0%"
                        y2="0%"
                      >
                        <Stop offset="8%" stopColor="#03CDF4" />
                        <Stop offset="38%" stopColor="#019BDE" />
                        <Stop offset="100%" stopColor="#01EBD0" />
                      </LinearGradient>
                    </Defs>
                    <SvgText
                      fill={`url(#${REAL_TIME_TITLE_GRADIENT_ID})`}
                      fontFamily={HOME_FONTS.bold}
                      fontSize={28}
                      x={0}
                      y={23}
                    >
                      Tudo bem!
                    </SvgText>
                  </Svg>
                </View>
              </View>
              <Text style={styles.realTimeMonitoringText}>
                O monitoramento{"\n"}está ativo.
              </Text>
            </View>
          </ExpoLinearGradient>
        </View>

        <View style={styles.section}>
          <ExpoLinearGradient
            colors={STATUS_CARD_GRADIENT_COLORS}
            locations={STATUS_CARD_GRADIENT_LOCATIONS}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 0 }}
            style={styles.emergencyButtonsContainer}
          >
            <Text style={styles.emergencyButtonsEstateText}>
              O AMBIENTE DOMÉSTICO ESTÁ SEGURO
            </Text>
            <Text style={styles.emergencyButtonsDescriptionText}>
              Monitoramento ativo para quedas, incêndios e brigas/agitação.
              Todos os sensores estão transmitindo dados em tempo real.
            </Text>
            <Pressable
              onPress={() => {
                console.log(`SAMU acionado`);
                openDialer("192");
              }}
              style={styles.emergencyButton}
            >
              <AmbulanceIcon />
              <Text style={styles.emergencyButtonText}>SAMU (192)</Text>
            </Pressable>
            <Pressable
              onPress={() => {
                console.log(`Policia acionada`);
                openDialer("190");
              }}
              style={styles.emergencyButton}
            >
              <PoliceIcon />
              <Text style={styles.emergencyButtonText}>Polícia (190)</Text>
            </Pressable>
            <Pressable
              onPress={() => {
                console.log(`Bombeiros acionados`);
                openDialer("193");
              }}
              style={styles.emergencyButton}
            >
              <FirefighterIcon />
              <Text style={styles.emergencyButtonText}>Bombeiros (193)</Text>
            </Pressable>
          </ExpoLinearGradient>
        </View>
      </ScrollView>
    </LayoutWithNavbar>
  );
}

function getAlertKind(notification: NotificationResponse): AlertItem["kind"] {
  const type = `${notification.notification_type} ${notification.title}`.toLowerCase();

  if (type.includes("fall") || type.includes("queda")) {
    return "fall";
  }

  if (type.includes("fight") || type.includes("briga")) {
    return "fight";
  }

  return "general";
}

function getAlertTitle(notification: NotificationResponse) {
  const kind = getAlertKind(notification);

  if (kind === "fall") {
    return "Queda";
  }

  if (kind === "fight") {
    return "Briga";
  }

  return notification.title || "Alerta";
}

function renderAlertIcon(notification: NotificationResponse) {
  const kind = getAlertKind(notification);

  if (kind === "fall") {
    return <FontAwesome6 color="#C9181F" name="person-falling" size={22} />;
  }

  if (kind === "fight") {
    return <Feather color="#06777D" name="alert-circle" size={28} />;
  }

  return <Feather color="#019BDE" name="alert-circle" size={28} />;
}

function notificationToAlert(notification: HomeAlert): AlertItem {
  const payload = notification.payload ?? {};
  const room =
    typeof payload.room === "string"
      ? payload.room
      : typeof payload.location === "string"
        ? payload.location
        : "Ambiente";
  const precision =
    typeof payload.precision === "number"
      ? payload.precision
      : typeof payload.confidence === "number"
        ? payload.confidence
        : 98;

  return {
    id: notification.id,
    imageUrl:
      typeof payload.image_url === "string"
        ? payload.image_url
        : "https://images.unsplash.com/photo-1581578731548-c64695cc6952?auto=format&fit=crop&w=900&q=80",
    isValidationAnswered: hasDetectionValidation(payload),
    kind: getAlertKind(notification),
    payload,
    precision,
    room,
    time: formatAlertTime(notification.created_at),
    title: getAlertTitle(notification),
  };
}

function formatAlertTime(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return date.toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatWorkspaceName(name: string) {
  return name.replace(/^Casa de\s+/i, "Workspace ");
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
