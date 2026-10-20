import { VARD_COLORS } from '../../../theme/vardTheme';
import { RouteProp, useFocusEffect, useRoute } from "@react-navigation/native";
import { Feather, FontAwesome6 } from "@expo/vector-icons";
import { BottomTabNavigationProp } from "@react-navigation/bottom-tabs";
import { useNavigation } from "@react-navigation/native";
import { LinearGradient as ExpoLinearGradient } from "expo-linear-gradient";
import { useVideoPlayer, VideoView } from "expo-video";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Linking,
  Modal,
  Pressable,
  RefreshControl,
  ScrollView,
  Text,
  View,
} from "react-native";
import { LayoutWithNavbar } from "../../../components/LayoutWithNavbar";
import { OccurrenceCard } from "../../../components/OccurrenceCard";
import {
  ApiRequestError,
  FallEventResponse,
  NotificationResponse,
  listFallEvents,
  listNotifications,
  listWorkspaces,
} from "../../../lib/api";
import {
  prefetchFallEventClip,
  prepareFallEventClip,
  removePreparedFallEventClip,
} from "../../../lib/fallClipPlayback";
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
  fallEvent?: FallEventResponse;
  workspaceName: string;
};

const STATUS_CARD_GRADIENT_COLORS = ["#00B9BB", "#00B9BB", "#003984"] as const;
const STATUS_CARD_GRADIENT_LOCATIONS = [0.08, 0.38, 1] as const;

const openDialer = (phoneNumber: string) => {
  Linking.openURL(`tel:${phoneNumber}`);
};

export function Home() {
  const route = useRoute<HomeRoute>();
  const navigation = useNavigation<HomeNavigation>();
  const accessToken = route.params?.accessToken ?? "";
  const clipPlayer = useVideoPlayer(null);
  const [alerts, setAlerts] = useState<HomeAlert[]>([]);
  const [isLoadingAlerts, setIsLoadingAlerts] = useState(true);
  const [isRefreshingAlerts, setIsRefreshingAlerts] = useState(false);
  const [alertsError, setAlertsError] = useState("");
  const [clipError, setClipError] = useState("");
  const [clipUri, setClipUri] = useState<string | null>(null);
  const [isClipVisible, setIsClipVisible] = useState(false);
  const [loadingClipId, setLoadingClipId] = useState<string | null>(null);
  const hasAlerts = alerts.length > 0;
  const visibleAlerts = alerts.slice(0, 2);
  const requestVersion = useRef(0);
  const statusColor = alertsError ? "#64748B" : hasAlerts ? "#C2410C" : VARD_COLORS.primary;
  const statusTitle = isLoadingAlerts ? "CONSULTANDO" : alertsError ? "SEM ATUALIZAÇÃO" : hasAlerts ? "ATENÇÃO" : "TUDO BEM!";
  const statusText = isLoadingAlerts
    ? "Verificando os alertas do seu ambiente."
    : alertsError
      ? "Não foi possível verificar as ocorrências."
      : hasAlerts
        ? `${alerts.length} ${alerts.length === 1 ? "alerta registrado nas últimas 24 horas. Confira os detalhes." : "alertas registrados nas últimas 24 horas. Confira os detalhes."}`
        : "Nenhum alerta nas últimas 24 horas. Acompanhando novas ocorrências.";

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
        workspaces.map(async (workspace) => {
          const [notifications, fallEvents] = await Promise.all([
            listNotifications(accessToken, workspace.id),
            listFallEvents(accessToken, workspace.id),
          ]);
          const fallEventByNotificationId = new Map(
            fallEvents
              .filter((event) => event.notification_id)
              .map((event) => [event.notification_id as string, event]),
          );
          return notifications.map((notification) => ({
            ...notification,
            fallEvent: fallEventByNotificationId.get(notification.id),
            workspaceName: workspace.name,
          }));
        }),
      );
      const now = Date.now();
      const cutoff = now - 24 * 60 * 60 * 1000;

      const notifications = workspaceNotifications
        .flat()
        .filter((notification) => {
          const createdAt = new Date(notification.created_at).getTime();
          return createdAt >= cutoff && createdAt <= now;
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
      const firstClip = notifications.find((alert) => alert.fallEvent?.has_clip)?.fallEvent;
      if (firstClip) prefetchFallEventClip(accessToken, firstClip.id);
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

  useEffect(() => () => removePreparedFallEventClip(clipUri), [clipUri]);

  function openAlertDetails(alert: HomeAlert) {
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
    );
  }

  async function openAlert(alert: HomeAlert) {
    const event = alert.fallEvent;
    if (!event?.has_clip) {
      openAlertDetails(alert);
      return;
    }

    if (loadingClipId) return;
    setLoadingClipId(event.id);
    setClipError("");
    try {
      const nextClipUri = await prepareFallEventClip(accessToken, event.id);
      await clipPlayer.replaceAsync(nextClipUri);
      clipPlayer.play();
      setClipUri(nextClipUri);
      setIsClipVisible(true);
    } catch (error) {
      setClipError(
        error instanceof ApiRequestError
          ? error.status === 401
            ? "Sua sessão expirou. Entre novamente para abrir o trecho."
            : error.message
          : error instanceof Error ? error.message : "Não foi possível abrir o trecho desta ocorrência.",
      );
    } finally {
      setLoadingClipId(null);
    }
  }

  async function closeClip() {
    clipPlayer.pause();
    setIsClipVisible(false);
    removePreparedFallEventClip(clipUri);
    setClipUri(null);
  }

  return (
    <LayoutWithNavbar>
      <ScrollView
        style={styles.scrollView}
        alwaysBounceVertical
        bounces
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            colors={["#00B9BB"]}
            onRefresh={handleRefresh}
            refreshing={isRefreshingAlerts}
            tintColor="#00B9BB"
          />
        }
        showsVerticalScrollIndicator={false}
      >
        <View>
          <View style={styles.alertsHeading}>
            <Text style={styles.sectionTitle}>Últimos Alertas</Text>
            <View style={styles.periodChip}>
              <Text style={styles.periodChipText}>Últimas 24h</Text>
            </View>
          </View>
          <View style={styles.alertsContainer}>
            {isLoadingAlerts ? (
              <View style={styles.noAlerts} accessibilityRole="progressbar" accessibilityLabel="Consultando alertas">
                <ActivityIndicator size="large" color="#00B9BB" />
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
                {visibleAlerts.map((alert) => <OccurrenceCard key={alert.id}
                  notification={alert} workspaceName={formatWorkspaceName(alert.workspaceName)} accessToken={accessToken}
                  canOpenClip={Boolean(alert.fallEvent?.has_clip)} opening={Boolean(loadingClipId && loadingClipId === alert.fallEvent?.id)}
                  onOpen={() => void openAlert(alert)} />)}
                {clipError ? <Text style={styles.clipError}>{clipError}</Text> : null}
              </View>
            ) : (
              <View
                accessibilityLabel="Nenhum incidente detectado nas últimas 24 horas"
                accessibilityRole="summary"
                style={styles.noAlerts}
              >
                <Feather name="check-circle" size={36} color="#A2ADB6" style={styles.noAlertsIcon} />
                <Text style={styles.noAlertsText}>
                  Nenhum incidente detectado{"\n"}nas últimas 24 horas.
                </Text>
              </View>
            )}
            {!isLoadingAlerts && !alertsError ? (
              <Pressable
                accessibilityRole="link"
                onPress={() => navigation.navigate("Alerts", {
                  accessToken,
                  screen: "RecentAlerts",
                  params: { accessToken },
                  userAvatarUrl: route.params?.userAvatarUrl,
                  userEmail: route.params?.userEmail ?? "",
                  userName: route.params?.userName,
                })}
                style={styles.moreOccurrencesLink}
              >
                <Text style={styles.moreOccurrencesText}>Ver mais</Text>
                <Feather name="chevron-right" size={16} color={VARD_COLORS.secondary} />
              </Pressable>
            ) : null}
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
      <Modal animationType="fade" onRequestClose={() => void closeClip()} transparent visible={isClipVisible}>
        <View style={styles.clipBackdrop}>
          <View style={styles.clipModal}>
            <View style={styles.clipHeader}>
              <View>
                <Text style={styles.clipEyebrow}>ALERTA</Text>
                <Text style={styles.clipTitle}>Trecho da queda</Text>
              </View>
              <Pressable accessibilityLabel="Fechar vídeo" onPress={() => void closeClip()} style={styles.clipClose}>
                <Feather color="#344054" name="x" size={21} />
              </Pressable>
            </View>
            <VideoView contentFit="contain" nativeControls player={clipPlayer} style={styles.clipVideo} />
          </View>
        </View>
      </Modal>
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
  return <Feather color="#00B9BB" name="bell" size={26} />;
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
        : payload.source === "accelerometer" ? 0 : 98;

  return {
    id: notification.id,
    imageUrl:
      typeof payload.image_url === "string"
        ? payload.image_url
        : payload.source === "accelerometer" ? "" : "https://images.unsplash.com/photo-1581578731548-c64695cc6952?auto=format&fit=crop&w=900&q=80",
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

function formatOccurrenceDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("pt-BR", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit",
    year: "numeric",
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
