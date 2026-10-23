import { VARD_COLORS } from "../../../theme/vardTheme";
import { RouteProp, useFocusEffect, useRoute } from "@react-navigation/native";
import { Feather } from "@expo/vector-icons";
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
import { styles, ui } from "../styles/Home";

import AmbulanceIcon from "../../../../assets/ambulance_icon.svg";
import FirefighterIcon from "../../../../assets/firefighters_icon.svg";
import PoliceIcon from "../../../../assets/police_icon.svg";

type HomeRoute = RouteProp<AppTabParamList, "Home">;
type HomeNavigation = BottomTabNavigationProp<AppTabParamList, "Home">;

type HomeAlert = NotificationResponse & {
  fallEvent?: FallEventResponse;
  workspaceId: string;
  workspaceName: string;
};

type AlertKind = "armed" | "fall" | "fight" | "general";

const STATUS_CARD_GRADIENT_COLORS = ["#00B9BB", "#00B9BB", "#003984"] as const;
const STATUS_CARD_GRADIENT_LOCATIONS = [0.08, 0.18, 0.7] as const;

const ALERT_RED = "#FF3B3B";
const ALERT_ORANGE = "#FF9020";

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
  const [defaultWorkspaceId, setDefaultWorkspaceId] = useState<string | null>(
    null,
  );
  // TODO: preencher com os dados reais de câmeras quando houver endpoint.
  const [cameraSummary] = useState<{ online: number; total: number } | null>(
    null,
  );
  const pendingValidation = alerts.filter(
    (alert) => !hasDetectionValidation(alert.payload ?? {}),
  ).length;

  const hasAlerts = alerts.length > 0;
  const visibleAlerts = alerts.slice(0, 2);
  const requestVersion = useRef(0);

  const statusColor = alertsError
    ? "#64748B"
    : hasAlerts
      ? ALERT_ORANGE
      : VARD_COLORS.primary;
  const statusTitle = isLoadingAlerts
    ? "CONSULTANDO"
    : alertsError
      ? "SEM ATUALIZAÇÃO"
      : hasAlerts
        ? "ATENÇÃO!"
        : "TUDO BEM!";
  const statusText = isLoadingAlerts
    ? "Verificando os alertas do seu ambiente."
    : alertsError
      ? "Não foi possível verificar as ocorrências."
      : hasAlerts
        ? `${alerts.length} ${alerts.length === 1 ? "alerta registrado nas últimas 24 horas." : "alertas registrados nas últimas 24 horas."}`
        : "Nenhum alerta nas últimas 24 horas. Acompanhando novas ocorrências.";
  const statusIcon = isLoadingAlerts
    ? "clock"
    : alertsError
      ? "wifi-off"
      : hasAlerts
        ? "alert-circle"
        : "check";

  const firstName = route.params?.userName?.trim().split(" ")[0];

  const loadAlerts = useCallback(
    async (silent = false) => {
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
        setDefaultWorkspaceId(workspaces[0]?.id ?? null);
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
              workspaceId: workspace.id,
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
        const firstClip = notifications.find(
          (alert) => alert.fallEvent?.has_clip,
        )?.fallEvent;
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
    },
    [accessToken],
  );

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

function goToRecentAlerts() {
  const workspaceId = alerts[0]?.workspaceId ?? defaultWorkspaceId;
  if (!workspaceId) return;

  navigation.navigate("Workspace", {
    accessToken,
    screen: "WorkspaceOccurrences",
    params: { accessToken, workspaceId },
    userAvatarUrl: route.params?.userAvatarUrl,
    userEmail: route.params?.userEmail ?? "",
    userName: route.params?.userName,
  });
}

  async function openClip(alert: HomeAlert) {
    const event = alert.fallEvent;
    if (!event?.has_clip) {
      setClipError("Esta ocorrência não possui trecho de vídeo.");
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
          : error instanceof Error
            ? error.message
            : "Não foi possível abrir o trecho desta ocorrência.",
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
        {/* Saudação */}
        <View style={ui.greetingBlock}>
          <Text style={ui.greetingTitle}>
            {getGreeting()},{" "}
            <Text style={ui.greetingBrand}>{firstName ?? "Vard.AI"}</Text>!
          </Text>
          <Text style={ui.greetingSubtitle}>Resumo das últimas 24h</Text>
        </View>

        {/* Resumo: alertas / câmeras / última atividade */}
        <View style={ui.summaryRow}>
          <SummaryCard
            icon="alert-circle"
            label="Alertas 24h:"
            value={isLoadingAlerts || alertsError ? "—" : String(alerts.length)}
          />
          <SummaryCard
            icon="help-circle"
            label="A validar:"
            value={
              isLoadingAlerts || alertsError ? "—" : String(pendingValidation)
            }
          />
          <SummaryCard
            icon="clock"
            label="Última atividade:"
            value={
              isLoadingAlerts || alertsError
                ? "—"
                : formatRelativeTime(alerts[0]?.created_at)
            }
          />
        </View>

        {/* Últimos alertas */}
        <Text style={ui.sectionTitle}>Últimos Alertas</Text>

        {isLoadingAlerts ? (
          <View
            style={ui.feedbackCard}
            accessibilityRole="progressbar"
            accessibilityLabel="Consultando alertas"
          >
            <ActivityIndicator size="large" color="#00B9BB" />
            <Text style={ui.feedbackText}>Consultando alertas…</Text>
          </View>
        ) : alertsError ? (
          <View style={ui.feedbackCard} accessibilityLiveRegion="polite">
            <Feather name="wifi-off" size={30} color="#64748B" />
            <Text style={ui.feedbackText}>{alertsError}</Text>
            <Pressable
              accessibilityRole="button"
              onPress={() => void loadAlerts()}
              style={ui.retryButton}
            >
              <Text style={ui.retryText}>Tentar novamente</Text>
            </Pressable>
          </View>
        ) : hasAlerts ? (
          <View style={ui.alertList}>
            {visibleAlerts.map((alert) => (
              <AlertCard
                key={alert.id}
                alert={alert}
                canOpenClip={Boolean(alert.fallEvent?.has_clip)}
                opening={Boolean(
                  loadingClipId && loadingClipId === alert.fallEvent?.id,
                )}
                onOpenClip={() => void openClip(alert)}
              />
            ))}
            {clipError ? <Text style={ui.clipError}>{clipError}</Text> : null}
          </View>
        ) : (
          <View
            accessibilityLabel="Nenhum incidente detectado nas últimas 24 horas"
            accessibilityRole="summary"
            style={ui.feedbackCard}
          >
            <Feather name="check-circle" size={34} color="#A2ADB6" />
            <Text style={ui.feedbackText}>
              Nenhum incidente detectado{"\n"}nas últimas 24 horas.
            </Text>
          </View>
        )}

        {!isLoadingAlerts && !alertsError ? (
          <Pressable
            accessibilityRole="link"
            onPress={goToRecentAlerts}
            style={ui.moreLink}
          >
            <Text style={ui.moreLinkText}>Ver mais</Text>
          </Pressable>
        ) : null}

        {/* Monitoramento em tempo real */}
        <Text style={ui.monitoringLabel}>MONITORAMENTO EM TEMPO REAL</Text>
        <Pressable
          accessibilityLiveRegion="polite"
          accessibilityRole="button"
          onPress={goToRecentAlerts}
          style={ui.statusCard}
        >
          <View style={[ui.statusAccent, { backgroundColor: statusColor }]} />
          <View
            style={[
              ui.statusIconCircle,
              { backgroundColor: `${statusColor}1F` },
            ]}
          >
            <Feather color={statusColor} name={statusIcon} size={20} />
          </View>
          <View style={ui.statusTextBlock}>
            <Text style={[ui.statusTitle, { color: statusColor }]}>
              {statusTitle}
            </Text>
            <Text style={ui.statusText}>{statusText}</Text>
          </View>
          <Feather
            name="chevron-right"
            size={22}
            color="#4B5563"
            style={ui.statusChevron}
          />
        </Pressable>

        {/* Ligações de emergência (inalterado) */}
        <View>
          <ExpoLinearGradient
            colors={STATUS_CARD_GRADIENT_COLORS}
            locations={STATUS_CARD_GRADIENT_LOCATIONS}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.emergencyButtonsContainer}
          >
            <Text style={styles.emergencyButtonsEstateText}>
              PRECISA DE AJUDA?
            </Text>
            <Text style={styles.emergencyButtonsDescriptionText}>
              Em caso de emergência, toque abaixo para ligar para o serviço
              adequado.
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

      <Modal
        animationType="fade"
        onRequestClose={() => void closeClip()}
        transparent
        visible={isClipVisible}
      >
        <View style={styles.clipBackdrop}>
          <View style={styles.clipModal}>
            <View style={styles.clipHeader}>
              <View>
                <Text style={styles.clipEyebrow}>ALERTA</Text>
                <Text style={styles.clipTitle}>Trecho da queda</Text>
              </View>
              <Pressable
                accessibilityLabel="Fechar vídeo"
                onPress={() => void closeClip()}
                style={styles.clipClose}
              >
                <Feather color="#344054" name="x" size={21} />
              </Pressable>
            </View>
            <VideoView
              contentFit="contain"
              nativeControls
              player={clipPlayer}
              style={styles.clipVideo}
            />
          </View>
        </View>
      </Modal>
    </LayoutWithNavbar>
  );
}

/* ------------------------------------------------------------------ */
/* Componentes locais                                                  */
/* ------------------------------------------------------------------ */

 const BRAND_GRADIENT = ["#00B9BB", "#003984"] as const;

type SummaryCardProps = {
  icon: React.ComponentProps<typeof Feather>["name"];
  label: string;
  value: string;
};

function SummaryCard({ icon, label, value }: SummaryCardProps) {
  return (
    <View style={ui.summaryCard}>
      <ExpoLinearGradient
        colors={BRAND_GRADIENT}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={ui.summaryIcon}
      >
        <Feather color="#FFFFFF" name={icon} size={17} />
      </ExpoLinearGradient>
      <View>
        <Text style={ui.summaryLabel}>{label}</Text>
        <Text style={ui.summaryValue} numberOfLines={1} adjustsFontSizeToFit>
          {value}
        </Text>
      </View>
    </View>
  );
}

type AlertCardProps = {
  alert: HomeAlert;
  canOpenClip: boolean;
  opening: boolean;
  onOpenClip: () => void;
};

function AlertCard({
  alert,
  canOpenClip,
  opening,
  onOpenClip,
}: AlertCardProps) {
  const kind = getAlertKind(alert);
  const accent =
    kind === "fight"
      ? ALERT_ORANGE
      : kind === "general"
        ? "#00B9BB"
        : ALERT_RED;

  return (
    <Pressable
      accessibilityRole="button"
      onPress={onOpenClip}
      style={ui.alertCard}
    >
      <View style={[ui.alertAccent, { backgroundColor: accent }]} />
      <View style={ui.alertBody}>
        <View style={ui.alertTop}>
          <View
            style={[ui.alertIconCircle, { backgroundColor: `${accent}22` }]}
          >
            <Feather color={accent} name="alert-triangle" size={17} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={[ui.alertTitle, { color: accent }]} numberOfLines={1}>
              {getAlertHeadline(alert)}
            </Text>
            <Text style={ui.alertTag} numberOfLines={1}>
              {alert.workspaceName.toUpperCase()}
            </Text>
          </View>
        </View>

        <Text style={ui.alertDescription}>{getAlertDescription(alert)}</Text>

        <View style={ui.alertFooter}>
          <Text style={ui.alertDate}>{formatShortDate(alert.created_at)}</Text>
          {canOpenClip ? (
            <Pressable
              accessibilityLabel="Ver trecho"
              accessibilityRole="button"
              disabled={opening}
              onPress={onOpenClip}
              style={ui.clipButton}
            >
              {opening ? (
                <ActivityIndicator size="small" color="#111827" />
              ) : (
                <>
                  <Feather name="play" size={10} color="#111827" />
                  <Text style={ui.clipButtonText}>Ver trecho</Text>
                </>
              )}
            </Pressable>
          ) : null}
        </View>
      </View>
    </Pressable>
  );
}

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Bom dia";
  if (hour < 18) return "Boa tarde";
  return "Boa noite";
}

function getAlertKind(notification: NotificationResponse): AlertKind {
  const type =
    `${notification.notification_type} ${notification.title}`.toLowerCase();

  if (type.includes("armed_person") || type.includes("pessoa armada"))
    return "armed";
  if (type.includes("fall") || type.includes("queda")) return "fall";
  if (
    type.includes("confrontation") ||
    type.includes("confronto") ||
    type.includes("fight") ||
    type.includes("briga")
  )
    return "fight";
  return "general";
}

function getAlertTitle(notification: NotificationResponse) {
  const kind = getAlertKind(notification);

  if (kind === "armed") return "Pessoa armada";
  if (kind === "fall") return "Queda";
  if (kind === "fight") return "Confronto";
  return notification.title || "Alerta";
}

function getAlertHeadline(notification: NotificationResponse) {
  const kind = getAlertKind(notification);
  if (kind === "armed") return "PESSOA ARMADA DETECTADA";
  if (kind === "fall") return "QUEDA DETECTADA";
  if (kind === "fight") return "CONFRONTO DETECTADO";
  return (notification.title || "Alerta").toUpperCase();
}

function getAlertDescription(notification: HomeAlert) {
  const payload = notification.payload ?? {};
  const camera =
    typeof payload.camera_name === "string"
      ? payload.camera_name
      : typeof payload.camera === "string"
        ? payload.camera
        : "";
  const where = camera ? `pela câmera ${camera}` : "pelo sistema";
  const kind = getAlertKind(notification);

  if (kind === "armed")
    return `Uma possível pessoa armada foi detectada ${where}`;
  if (kind === "fall") return `Uma possível queda foi detectada ${where}`;
  if (kind === "fight") return `Um possível confronto foi detectado ${where}`;
  return notification.title || "Novo alerta registrado.";
}

function formatAlertTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/** "22/11, 23:15" */
function formatShortDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(date.getDate())}/${pad(date.getMonth() + 1)}, ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** "há 12 min", "há 3 h" */
function formatRelativeTime(value?: string) {
  if (!value) return "—";
  const time = new Date(value).getTime();
  if (Number.isNaN(time)) return "—";
  const minutes = Math.max(0, Math.floor((Date.now() - time) / 60_000));
  if (minutes < 1) return "agora";
  if (minutes < 60) return `há ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `há ${hours} h`;
  return `há ${Math.floor(hours / 24)} d`;
}

function hasDetectionValidation(payload: Record<string, unknown>) {
  const validation = payload.detection_validation;

  if (!validation || typeof validation !== "object") return false;

  const validationPayload = validation as Record<string, unknown>;

  return (
    typeof validationPayload.is_valid === "boolean" ||
    typeof validationPayload.answered_at === "string"
  );
}
