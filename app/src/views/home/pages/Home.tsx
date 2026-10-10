import { RouteProp, useFocusEffect, useRoute } from "@react-navigation/native";
import { Feather, FontAwesome6 } from "@expo/vector-icons";
import { BottomTabNavigationProp } from "@react-navigation/bottom-tabs";
import { useNavigation } from "@react-navigation/native";
import { LinearGradient as ExpoLinearGradient } from "expo-linear-gradient";
import { useCallback, useRef, useState } from "react";
import {
  ActivityIndicator,
  Linking,
  Pressable,
  RefreshControl,
  ScrollView,
  Text,
  View,
} from "react-native";
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
  styles,
} from "../styles/Home";

import AmbulanceIcon from "../../../../assets/ambulance_icon.svg";
import FirefighterIcon from "../../../../assets/firefighters_icon.svg";
import PoliceIcon from "../../../../assets/police_icon.svg";

type HomeRoute = RouteProp<AppTabParamList, "Home">;
type HomeNavigation = BottomTabNavigationProp<AppTabParamList, "Home">;

type HomeAlert = NotificationResponse & {
  workspaceName: string;
};

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
  const requestVersion = useRef(0);
  const statusColor = alertsError ? "#64748B" : hasAlerts ? "#C2410C" : "#00ACC8";
  const statusTitle = isLoadingAlerts ? "CONSULTANDO" : alertsError ? "SEM ATUALIZAÇÃO" : hasAlerts ? "ATENÇÃO" : "TUDO BEM!";
  const statusText = isLoadingAlerts
    ? "Verificando os alertas do seu ambiente."
    : alertsError
      ? "Não foi possível verificar as ocorrências."
      : hasAlerts
        ? `${alerts.length} ${alerts.length === 1 ? "alerta registrado hoje. Confira os detalhes." : "alertas registrados hoje. Confira os detalhes."}`
        : "Nenhum alerta hoje. Acompanhando novas ocorrências.";

  const loadAlerts = useCallback(async (silent = false) => {
    const version = ++requestVersion.current;
    if (!accessToken) {
      setAlerts([]);
      setAlertsError("Sessão inválida. Faça login novamente.");
      setIsLoadingAlerts(false);
      return;
    }

    try {
      if (!silent) setIsLoadingAlerts(true);
      const workspaces = await listWorkspaces(accessToken);
      if (version !== requestVersion.current) return;

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

      if (version !== requestVersion.current) return;
      setAlertsError("");
      setAlerts(notifications);
    } catch (error) {
      if (version !== requestVersion.current) return;
      setAlertsError(
        error instanceof ApiRequestError
          ? error.message
          : "Não foi possível carregar os alertas.",
      );
    } finally {
      if (version === requestVersion.current) setIsLoadingAlerts(false);
    }
  }, [accessToken]);

  useFocusEffect(
    useCallback(() => {
      void loadAlerts();
      const timer = setInterval(() => void loadAlerts(true), 30_000);
      return () => {
        clearInterval(timer);
        requestVersion.current += 1;
      };
    }, [loadAlerts]),
  );

  const handleRefresh = useCallback(async () => {
    setIsRefreshingAlerts(true);
    try {
      await loadAlerts(true);
    } finally {
      setIsRefreshingAlerts(false);
    }
  }, [loadAlerts]);

  return (
    <LayoutWithNavbar>
      <ScrollView
        style={styles.scrollView}
        alwaysBounceVertical
        bounces
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
            {isLoadingAlerts ? (
              <View style={styles.noAlerts} accessibilityRole="progressbar" accessibilityLabel="Consultando alertas">
                <ActivityIndicator size="large" color="#019BDE" />
                <Text style={[styles.noAlertsText, styles.feedbackText]}>Consultando alertas…</Text>
              </View>
            ) : alertsError ? (
              <View style={[styles.noAlerts, styles.errorCard]} accessibilityLiveRegion="polite">
                <Feather name="wifi-off" size={32} color="#64748B" />
                <Text style={[styles.noAlertsText, styles.feedbackText]}>{alertsError}</Text>
                <Pressable accessibilityRole="button" onPress={() => void loadAlerts()} style={styles.retryButton}>
                  <Text style={styles.retryText}>Tentar novamente</Text>
                </Pressable>
              </View>
            ) : hasAlerts ? (
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
                      index < visibleAlerts.length - 1 && styles.alertRowBorder,
                      pressed && styles.alertButtonPressed,
                    ]}
                  >
                    <View style={styles.alertIconWrap}>
                      {renderAlertIcon(alert)}
                    </View>
                    <View style={styles.alertTextWrap}>
                      <Text style={styles.alertTitle} numberOfLines={2}>
                        {getAlertTitle(alert)}
                      </Text>
                      <Text style={styles.alertWorkspace} numberOfLines={1}>
                        {formatWorkspaceName(alert.workspaceName)}
                      </Text>
                    </View>
                    <Feather color="#737B84" name="chevron-right" size={26} />
                  </Pressable>
                ))}
              </View>
            ) : (
              <View
                accessibilityLabel="Nenhum incidente detectado hoje"
                accessibilityRole="summary"
                style={styles.noAlerts}
              >
                <Feather name="check-circle" size={36} color="#A2ADB6" style={styles.noAlertsIcon} />
                <Text style={styles.noAlertsText}>
                  Nenhum incidente{"\n"}detectado hoje.
                </Text>
              </View>
            )}
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.monitoringLabel}>MONITORAMENTO EM TEMPO REAL</Text>
          <View style={[styles.realTimeMonitoringBorder, { backgroundColor: statusColor }]}>
            <View style={styles.realTimeMonitoringContainer} accessibilityLiveRegion="polite">
              <View style={styles.realTimeMonitoringHeader}>
                <View style={[styles.realTimeCheckIcon, { backgroundColor: statusColor }]}>
                  <Feather color="#FFFFFF" name={isLoadingAlerts ? "clock" : alertsError ? "wifi-off" : hasAlerts ? "alert-triangle" : "check"} size={18} />
                </View>
                <Text style={[styles.statusTitle, { color: statusColor }]}>{statusTitle}</Text>
              </View>
              <Text style={styles.realTimeMonitoringText}>{statusText}</Text>
            </View>
          </View>
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
              PRECISA DE AJUDA?
            </Text>
            <Text style={styles.emergencyButtonsDescriptionText}>
              Em caso de emergência, toque abaixo para ligar para o serviço adequado.
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
                console.log(`Polícia acionada`);
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

  if (type.includes("armed_person") || type.includes("pessoa armada")) {
    return "armed";
  }

  if (type.includes("fall") || type.includes("queda")) {
    return "fall";
  }

  if (type.includes("confrontation") || type.includes("confronto") || type.includes("fight") || type.includes("briga")) {
    return "fight";
  }

  return "general";
}

function getAlertTitle(notification: NotificationResponse) {
  const kind = getAlertKind(notification);

  if (kind === "armed") {
    return "Pessoa armada";
  }

  if (kind === "fall") {
    return "Queda";
  }

  if (kind === "fight") {
    return "Confronto";
  }

  return notification.title || "Alerta";
}

function renderAlertIcon(notification: NotificationResponse) {
  const kind = getAlertKind(notification);

  if (kind === "armed") {
    return <FontAwesome6 color="#C9181F" name="gun" size={23} />;
  }

  if (kind === "fall") {
    return <FontAwesome6 color="#C9181F" name="person-falling" size={22} />;
  }

  if (kind === "fight") {
    return <FontAwesome6 color="#B45309" name="hand-fist" size={24} />;
  }

  if (/fire|incêndio|incendio|fogo/i.test(`${notification.notification_type} ${notification.title}`)) {
    return <FontAwesome6 color="#EA580C" name="fire-flame-curved" size={25} />;
  }
  return <Feather color="#019BDE" name="bell" size={26} />;
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
