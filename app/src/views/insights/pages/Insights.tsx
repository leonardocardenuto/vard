import { Ionicons } from "@expo/vector-icons";
import { RouteProp, useRoute } from "@react-navigation/native";
import { useFonts } from "expo-font";
import { LinearGradient as ExpoLinearGradient } from "expo-linear-gradient";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Animated,
  Modal,
  PanResponder,
  Platform,
  Pressable,
  ScrollView,
  Text,
  View,
} from "react-native";
import Svg, {
  Circle,
  Defs,
  G,
  LinearGradient,
  Line,
  Path,
  Rect,
  Stop,
  Text as SvgText,
} from "react-native-svg";

import { LayoutWithNavbar } from "../../../components/LayoutWithNavbar";
import {
  ApiRequestError,
  CameraResponse,
  NotificationResponse,
  WorkspaceResponse,
  listCameras,
  listNotifications,
  listWorkspaces,
} from "../../../lib/api";
import { AppTabParamList } from "../../../navigation/types";
import {
  INSIGHTS_COLORS,
  INSIGHTS_FONTS,
  INSIGHTS_GRADIENT_COLORS,
  INSIGHTS_GRADIENT_LOCATIONS,
  styles,
} from "../styles/Insights";

type Period = "Ultimos 15 dias" | "Ultimos 30 dias" | "Ultimos 60 dias" | "Ultimos 90 dias";
type CameraFilter = string;
type InsightsRoute = RouteProp<AppTabParamList, "Insights">;

type CameraData = {
  activityLabel: string;
  chartValues: number[];
  incidentTotal: number;
  roomIncidents: Array<{
    room: string;
    value: number;
    barStyle: object;
  }>;
};

const PERIOD_OPTIONS: Period[] = [
  "Ultimos 15 dias",
  "Ultimos 30 dias",
  "Ultimos 60 dias",
  "Ultimos 90 dias",
];

const DEFAULT_PERIOD: Period = "Ultimos 90 dias";
const ALL_CAMERAS_FILTER = "Todas";

const ACTIVITY_SEGMENTS = [
  styles.activitySegmentFirst,
  styles.activitySegmentSecond,
  styles.activitySegmentThird,
];

const PERIOD_DAYS: Record<Period, number> = {
  "Ultimos 15 dias": 15,
  "Ultimos 30 dias": 30,
  "Ultimos 60 dias": 60,
  "Ultimos 90 dias": 90,
};

export function Insights() {
  const route = useRoute<InsightsRoute>();
  const accessToken = route.params?.accessToken ?? "";
  const [fontsLoaded] = useFonts({
    [INSIGHTS_FONTS.regular]: require("../../../../assets/fonts/Poppins-Regular.ttf"),
    [INSIGHTS_FONTS.medium]: require("../../../../assets/fonts/Poppins-Medium.ttf"),
    [INSIGHTS_FONTS.semiBold]: require("../../../../assets/fonts/Poppins-SemiBold.ttf"),
    [INSIGHTS_FONTS.bold]: require("../../../../assets/fonts/Poppins-Bold.ttf"),
    [INSIGHTS_FONTS.extraBold]: require("../../../../assets/fonts/Poppins-ExtraBold.ttf"),
    [INSIGHTS_FONTS.black]: require("../../../../assets/fonts/Poppins-Black.ttf"),
  });
  const [period, setPeriod] = useState<Period | null>(DEFAULT_PERIOD);
  const [selectedCamera, setSelectedCamera] = useState<CameraFilter | null>(null);
  const [isFilterSheetOpen, setIsFilterSheetOpen] = useState(false);
  const [isWorkspaceMenuOpen, setIsWorkspaceMenuOpen] = useState(false);
  const [workspaces, setWorkspaces] = useState<WorkspaceResponse[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string | null>(null);
  const [cameras, setCameras] = useState<CameraResponse[]>([]);
  const [notifications, setNotifications] = useState<NotificationResponse[]>([]);
  const [isLoadingInsights, setIsLoadingInsights] = useState(true);
  const [insightsError, setInsightsError] = useState("");
  const [exportLabel, setExportLabel] = useState("Export Monthly Report");
  const sheetAnimation = useRef(new Animated.Value(0)).current;
  const sheetDragY = useRef(new Animated.Value(0)).current;

  const effectivePeriod = period ?? DEFAULT_PERIOD;
  const effectiveCamera = selectedCamera ?? ALL_CAMERAS_FILTER;
  const selectedWorkspace = useMemo(
    () => workspaces.find((workspace) => workspace.id === selectedWorkspaceId) ?? workspaces[0],
    [selectedWorkspaceId, workspaces],
  );
  const cameraOptions = useMemo(
    () => [ALL_CAMERAS_FILTER, ...cameras.map((camera) => camera.name)],
    [cameras],
  );
  const selectedData = useMemo(
    () => buildInsightsData({
      cameras,
      cameraName: effectiveCamera,
      notifications,
      period: effectivePeriod,
    }),
    [cameras, effectiveCamera, effectivePeriod, notifications],
  );

  useEffect(() => {
    async function loadWorkspaces() {
      if (!accessToken) {
        setInsightsError("Sessao invalida. Faca login novamente.");
        setIsLoadingInsights(false);
        return;
      }

      try {
        setInsightsError("");
        setIsLoadingInsights(true);
        const workspaceList = await listWorkspaces(accessToken);
        setWorkspaces(workspaceList);
        setSelectedWorkspaceId((current) => current ?? workspaceList[0]?.id ?? null);
      } catch (error) {
        setInsightsError(
          error instanceof ApiRequestError ? error.message : "Nao foi possivel carregar os workspaces."
        );
        setIsLoadingInsights(false);
      }
    }

    void loadWorkspaces();
  }, [accessToken]);

  useEffect(() => {
    async function loadWorkspaceInsights() {
      if (!accessToken || !selectedWorkspace) {
        setCameras([]);
        setNotifications([]);
        setIsLoadingInsights(false);
        return;
      }

      try {
        setInsightsError("");
        setIsLoadingInsights(true);
        const [workspaceCameras, workspaceNotifications] = await Promise.all([
          listCameras(accessToken, selectedWorkspace.id),
          listNotifications(accessToken, selectedWorkspace.id),
        ]);
        setCameras(workspaceCameras);
        setNotifications(workspaceNotifications);
        setSelectedCamera((current) => {
          if (!current || current === ALL_CAMERAS_FILTER) {
            return current;
          }
          return workspaceCameras.some((camera) => camera.name === current) ? current : null;
        });
      } catch (error) {
        setInsightsError(
          error instanceof ApiRequestError ? error.message : "Nao foi possivel carregar os insights."
        );
      } finally {
        setIsLoadingInsights(false);
      }
    }

    void loadWorkspaceInsights();
  }, [accessToken, selectedWorkspace]);

  useEffect(() => {
    Animated.timing(sheetAnimation, {
      toValue: isFilterSheetOpen ? 1 : 0,
      duration: isFilterSheetOpen ? 280 : 220,
      useNativeDriver: true,
    }).start();
  }, [isFilterSheetOpen, sheetAnimation]);

  function openFilterSheet() {
    sheetDragY.setValue(0);
    setIsFilterSheetOpen(true);
  }

  function closeFilterSheet() {
    Animated.timing(sheetAnimation, {
      toValue: 0,
      duration: 220,
      useNativeDriver: true,
    }).start(({ finished }) => {
      if (finished) {
        sheetDragY.setValue(0);
        setIsFilterSheetOpen(false);
      }
    });
  }

  function togglePeriodFilter(nextPeriod: Period) {
    setPeriod((currentPeriod) => (currentPeriod === nextPeriod ? null : nextPeriod));
  }

  function toggleCameraFilter(nextCamera: CameraFilter) {
    if (nextCamera === ALL_CAMERAS_FILTER) {
      setSelectedCamera(null);
      return;
    }
    setSelectedCamera((currentCamera) => (currentCamera === nextCamera ? null : nextCamera));
  }

  const panResponder = useRef(
    PanResponder.create({
      onMoveShouldSetPanResponder: (_, gestureState) =>
        Math.abs(gestureState.dy) > Math.abs(gestureState.dx) && gestureState.dy > 8,
      onPanResponderMove: (_, gestureState) => {
        sheetDragY.setValue(Math.max(0, gestureState.dy));
      },
      onPanResponderRelease: (_, gestureState) => {
        if (gestureState.dy > 120 || gestureState.vy > 1.1) {
          closeFilterSheet();
          return;
        }

        Animated.spring(sheetDragY, {
          toValue: 0,
          damping: 18,
          mass: 0.9,
          stiffness: 180,
          useNativeDriver: true,
        }).start();
      },
      onPanResponderTerminate: () => {
        Animated.spring(sheetDragY, {
          toValue: 0,
          damping: 18,
          mass: 0.9,
          stiffness: 180,
          useNativeDriver: true,
        }).start();
      },
    }),
  ).current;

  if (!fontsLoaded) {
    return null;
  }

  function handleExportReport() {
    const report = buildExportReport({
      cameraName: effectiveCamera,
      cameras,
      data: selectedData,
      notifications: filterNotificationsBySelection({
        cameras,
        cameraName: effectiveCamera,
        notifications,
        period: effectivePeriod,
      }),
      period: effectivePeriod,
      workspaceName: selectedWorkspace?.name ?? "Workspace",
    });
    const fileName = `vard-insights-${slugify(selectedWorkspace?.name ?? "workspace")}-${Date.now()}.csv`;

    if (Platform.OS === "web" && typeof document !== "undefined") {
      const blob = new Blob([report], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = fileName;
      link.click();
      URL.revokeObjectURL(url);
      setExportLabel("Relatorio exportado");
      return;
    }

    setExportLabel("Relatorio pronto");
    Alert.alert(
      "Relatorio gerado",
      `Workspace: ${selectedWorkspace?.name ?? "Workspace"}\nPeriodo: ${effectivePeriod}\nCamera: ${effectiveCamera}\nIncidentes: ${selectedData.incidentTotal}`,
    );
  }

  const sheetTranslateY = sheetAnimation.interpolate({
    inputRange: [0, 1],
    outputRange: [460, 0],
  });

  const bottomSheetTranslateY = Animated.add(sheetTranslateY, sheetDragY);

  const backdropOpacity = sheetAnimation.interpolate({
    inputRange: [0, 1],
    outputRange: [0, 0.4],
  });

  function toggleWorkspaceMenu() {
    setIsWorkspaceMenuOpen((currentState) => !currentState);
  }

  function handleWorkspaceSelect(workspaceId: string) {
    setSelectedWorkspaceId(workspaceId);
    setIsWorkspaceMenuOpen(false);
  }

  return (
    <LayoutWithNavbar>
      <View style={styles.page}>
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.screen}>
            <View style={styles.hero}>
              {isWorkspaceMenuOpen ? (
                <Pressable
                  onPress={() => {
                    setIsWorkspaceMenuOpen(false);
                  }}
                  style={styles.heroDismissLayer}
                />
              ) : null}
              <View style={styles.heroTopRow}>
                <GradientTitle
                  fontFamily={INSIGHTS_FONTS.semiBold}
                  fontSize={40}
                  height={42}
                  style={styles.title}
                  text="Insights"
                  width={160}
                  y={31}
                />
                <View style={styles.heroWorkspaceArea}>
                  <Pressable
                    accessibilityLabel="Selecionar workspace"
                    accessibilityRole="button"
                    onPress={toggleWorkspaceMenu}
                    style={({ pressed }) => [
                      styles.heroChip,
                      pressed && styles.pressed,
                    ]}
                  >
                    <Text
                      ellipsizeMode="tail"
                      numberOfLines={1}
                      style={styles.heroChipText}
                    >
                      {selectedWorkspace?.name ?? "Selecione"}
                    </Text>
                    <Ionicons
                      color={INSIGHTS_COLORS.gradientMiddle}
                      name={isWorkspaceMenuOpen ? "chevron-up" : "chevron-down"}
                      size={18}
                    />
                  </Pressable>

                  {isWorkspaceMenuOpen ? (
                    <View style={styles.workspaceMenu}>
                      {workspaces.length === 0 ? (
                        <Text style={styles.workspaceMenuItemText}>
                          Nenhum workspace encontrado
                        </Text>
                      ) : null}
                      {workspaces.map((workspace) => {
                        const isSelected =
                          workspace.id === selectedWorkspace?.id;

                        return (
                          <Pressable
                            accessibilityRole="button"
                            key={workspace.id}
                            onPress={() => handleWorkspaceSelect(workspace.id)}
                            style={({ pressed }) => [
                              styles.workspaceMenuItem,
                              isSelected && styles.workspaceMenuItemSelected,
                              pressed && styles.pressed,
                            ]}
                          >
                            <Text
                              numberOfLines={1}
                              style={[
                                styles.workspaceMenuItemText,
                                isSelected &&
                                  styles.workspaceMenuItemTextSelected,
                              ]}
                            >
                              {workspace.name}
                            </Text>
                            {isSelected ? (
                              <Ionicons
                                color={INSIGHTS_COLORS.gradientMiddle}
                                name="checkmark"
                                size={16}
                              />
                            ) : null}
                          </Pressable>
                        );
                      })}
                    </View>
                  ) : null}
                </View>
              </View>
              <Text style={styles.subtitle}>
                Resumo de atividades e saude do dia.
              </Text>
              {insightsError ? (
                <Text style={styles.activeFilterText}>{insightsError}</Text>
              ) : null}
              {isLoadingInsights ? (
                <View style={styles.activeFiltersSummary}>
                  <ActivityIndicator color={INSIGHTS_COLORS.gradientMiddle} />
                </View>
              ) : null}
            </View>

            <View style={styles.cardLarge}>
              <View style={styles.incidentsHeader}>
                <View>
                  <Text style={styles.cardTitle}>Incidentes</Text>
                  <Text style={styles.cardSubtitle}>Incidentes x Dias</Text>
                </View>

                <View style={styles.incidentsControls}>
                  <Pressable
                    accessibilityLabel="Abrir filtros"
                    accessibilityRole="button"
                    onPress={openFilterSheet}
                    style={({ pressed }) => [
                      styles.filterButton,
                      pressed && styles.pressed,
                    ]}
                  >
                    <Ionicons color="#000000" name="filter-outline" size={20} />
                    <Text style={styles.filterButtonText}>Filtros</Text>
                  </Pressable>
                </View>
              </View>

              <IncidentsChart values={selectedData.chartValues} />
            </View>

            <View style={styles.cardRooms}>
              <Text style={styles.roomsTitle}>Incidentes por Comodo</Text>
              <View style={styles.roomList}>
                {selectedData.roomIncidents.map((item) => (
                  <View key={item.room} style={styles.roomItem}>
                    <View style={styles.roomTopLine}>
                      <Text style={styles.roomName}>{item.room}</Text>
                      <Text style={styles.roomValue}>{item.value}</Text>
                    </View>
                    <View style={styles.roomTrack}>
                      <View style={[styles.roomBar, item.barStyle]} />
                    </View>
                  </View>
                ))}
              </View>
            </View>

            <View style={styles.dailyCard}>
              <View style={styles.dailyBadge}>
                <Ionicons
                  color={INSIGHTS_COLORS.gradientMiddle}
                  name="ribbon-outline"
                  size={40}
                />
              </View>
              <Text style={styles.dailyLabel}>TOTAL DAILY INCIDENTS</Text>
              <Text style={styles.dailyValue}>
                {selectedData.incidentTotal}
              </Text>
              <Text style={styles.dailyText}>
                Nenhuma anomalia detectada nas ultimas 24 horas.
              </Text>
            </View>

            <GradientTitle
              fontFamily={INSIGHTS_FONTS.semiBold}
              fontSize={40}
              height={52}
              style={styles.activityTitle}
              text="Atividade"
              width={200}
              y={39}
            />

            <View style={styles.activityCard}>
              <Text style={styles.cameraTitle}>
                {selectedData.activityLabel}
              </Text>
              <Text style={styles.cameraSubtitle}>Ultimas 24 horas</Text>
              <View style={styles.activityChart}>
                <View style={styles.activityTrack}>
                  {ACTIVITY_SEGMENTS.map((segmentStyle, index) => (
                    <View
                      key={index}
                      style={[styles.activitySegment, segmentStyle]}
                    />
                  ))}
                </View>
                <View style={styles.activityGrid}>
                  {["00h", "06h00", "12h00", "18h00", "23h59"].map((time) => (
                    <View key={time} style={styles.activityTick}>
                      <View style={styles.activityDash} />
                      <Text style={styles.activityTime}>{time}</Text>
                    </View>
                  ))}
                </View>
              </View>

              <View style={styles.legend}>
                <View style={styles.legendRow}>
                  <View style={styles.legendActiveDot} />
                  <Text style={styles.legendText}>Ativo</Text>
                </View>
                <View style={styles.legendRow}>
                  <View style={styles.legendInactiveDot} />
                  <Text style={styles.legendText}>Inativo</Text>
                </View>
              </View>
            </View>

            <Pressable
              accessibilityLabel="Exportar relatorio mensal em PDF"
              accessibilityRole="button"
              onPress={handleExportReport}
              style={({ pressed }) => [
                styles.exportButton,
                pressed && styles.pressed,
              ]}
            >
              <ExpoLinearGradient
                colors={INSIGHTS_GRADIENT_COLORS}
                end={{ x: 1, y: 0 }}
                locations={INSIGHTS_GRADIENT_LOCATIONS}
                start={{ x: 0, y: 0 }}
                style={styles.exportGradient}
              >
                <Ionicons color="#FFFFFF" name="documents-outline" size={25} />
                <Text style={styles.exportText}>{exportLabel}</Text>
              </ExpoLinearGradient>
            </Pressable>
          </View>
        </ScrollView>

        <Modal
          animationType="none"
          onRequestClose={closeFilterSheet}
          transparent
          visible={isFilterSheetOpen}
        >
          <View style={styles.bottomSheetRoot}>
            <Pressable
              accessibilityLabel="Fechar filtros"
              accessibilityRole="button"
              onPress={closeFilterSheet}
              style={styles.bottomSheetBackdropPressable}
            >
              <Animated.View
                pointerEvents="none"
                style={[
                  styles.bottomSheetBackdrop,
                  { opacity: backdropOpacity },
                ]}
              />
            </Pressable>

            <Animated.View
              {...panResponder.panHandlers}
              style={[
                styles.bottomSheetContainer,
                { transform: [{ translateY: bottomSheetTranslateY }] },
              ]}
            >
              <View style={styles.bottomSheetHandle} />
              <Text style={styles.bottomSheetTitle}>Filtrar por</Text>

              <Text style={styles.bottomSheetSectionTitle}>Período</Text>
              <View style={styles.bottomSheetOptions}>
                {PERIOD_OPTIONS.map((item) => (
                  <FilterOptionButton
                    iconName="calendar-clear-outline"
                    key={item}
                    label={item}
                    onPress={() => togglePeriodFilter(item)}
                    selected={item === period}
                  />
                ))}
              </View>

              <Text style={styles.bottomSheetSectionTitle}>Câmeras</Text>
              <View style={styles.bottomSheetOptions}>
                {cameraOptions.map((item) => (
                  <FilterOptionButton
                    iconName="videocam-outline"
                    key={item}
                    label={item}
                    onPress={() => toggleCameraFilter(item)}
                    selected={item === effectiveCamera}
                  />
                ))}
              </View>

              <Pressable
                accessibilityRole="button"
                onPress={closeFilterSheet}
                style={({ pressed }) => [
                  styles.filterApplyButton,
                  pressed && styles.pressed,
                ]}
              >
                <Text style={styles.filterApplyButtonText}>
                  Aplicar filtros
                </Text>
              </Pressable>
            </Animated.View>
          </View>
        </Modal>
      </View>
    </LayoutWithNavbar>
  );
}

function buildInsightsData({
  cameras,
  cameraName,
  notifications,
  period,
}: {
  cameras: CameraResponse[];
  cameraName: string;
  notifications: NotificationResponse[];
  period: Period;
}): CameraData {
  const { filteredNotifications, now, startTime } = filterNotificationsBySelection({
    cameras,
    cameraName,
    notifications,
    period,
    withBounds: true,
  });
  const camerasById = new Map(cameras.map((camera) => [camera.id, camera]));
  const selectedCamera = cameras.find((camera) => camera.name === cameraName);

  const bucketCount = 8;
  const bucketSize = Math.max(1, (now - startTime) / bucketCount);
  const chartValues = Array.from({ length: bucketCount }, () => 0);
  filteredNotifications.forEach((notification) => {
    const createdAt = new Date(notification.created_at).getTime();
    const bucketIndex = Math.min(bucketCount - 1, Math.max(0, Math.floor((createdAt - startTime) / bucketSize)));
    chartValues[bucketIndex] += 1;
  });

  const roomCounts = new Map<string, number>();
  filteredNotifications.forEach((notification) => {
    const payloadRoom = notification.payload?.room;
    const camera = notification.camera_id ? camerasById.get(notification.camera_id) : undefined;
    const room =
      typeof payloadRoom === "string" && payloadRoom.trim()
        ? payloadRoom.trim()
        : camera?.name ?? notification.notification_type;
    roomCounts.set(room, (roomCounts.get(room) ?? 0) + 1);
  });

  const maxRoomValue = Math.max(1, ...roomCounts.values());
  const roomIncidents = Array.from(roomCounts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
    .map(([room, value], index) => ({
      room,
      value,
      barStyle: {
        backgroundColor:
          index % 3 === 0
            ? INSIGHTS_COLORS.gradientEnd
            : index % 3 === 1
              ? INSIGHTS_COLORS.gradientStart
              : INSIGHTS_COLORS.gradientMiddle,
        width: `${Math.max(8, Math.round((value / maxRoomValue) * 100))}%`,
      },
    }));

  return {
    activityLabel: selectedCamera?.name ? `Camera ${selectedCamera.name}` : "Todas as cameras",
    chartValues,
    incidentTotal: filteredNotifications.length,
    roomIncidents:
      roomIncidents.length > 0
        ? roomIncidents
        : [{ room: "Sem incidentes", value: 0, barStyle: { width: "0%" } }],
  };
}

function filterNotificationsBySelection(params: {
  cameras: CameraResponse[];
  cameraName: string;
  notifications: NotificationResponse[];
  period: Period;
}): NotificationResponse[];
function filterNotificationsBySelection(params: {
  cameras: CameraResponse[];
  cameraName: string;
  notifications: NotificationResponse[];
  period: Period;
  withBounds: true;
}): { filteredNotifications: NotificationResponse[]; now: number; startTime: number };
function filterNotificationsBySelection({
  cameras,
  cameraName,
  notifications,
  period,
  withBounds,
}: {
  cameras: CameraResponse[];
  cameraName: string;
  notifications: NotificationResponse[];
  period: Period;
  withBounds?: true;
}) {
  const now = Date.now();
  const startTime = now - PERIOD_DAYS[period] * 24 * 60 * 60 * 1000;
  const selectedCamera = cameras.find((camera) => camera.name === cameraName);
  const filteredNotifications = notifications.filter((notification) => {
    const createdAt = new Date(notification.created_at).getTime();
    const isInsidePeriod = Number.isFinite(createdAt) && createdAt >= startTime;
    const matchesCamera =
      cameraName === ALL_CAMERAS_FILTER || notification.camera_id === selectedCamera?.id;

    return isInsidePeriod && matchesCamera;
  });

  if (withBounds) {
    return { filteredNotifications, now, startTime };
  }

  return filteredNotifications;
}

function buildExportReport({
  cameraName,
  cameras,
  data,
  notifications,
  period,
  workspaceName,
}: {
  cameraName: string;
  cameras: CameraResponse[];
  data: CameraData;
  notifications: NotificationResponse[];
  period: Period;
  workspaceName: string;
}) {
  const camerasById = new Map(cameras.map((camera) => [camera.id, camera.name]));
  const rows = [
    ["workspace", workspaceName],
    ["periodo", period],
    ["camera", cameraName],
    ["total_incidentes", String(data.incidentTotal)],
    [],
    ["data", "camera", "tipo", "severidade", "titulo", "descricao"],
    ...notifications.map((notification) => [
      new Date(notification.created_at).toLocaleString("pt-BR"),
      notification.camera_id ? camerasById.get(notification.camera_id) ?? "Camera removida" : "Sem camera",
      notification.notification_type,
      notification.severity,
      notification.title,
      notification.body,
    ]),
  ];

  return rows.map((row) => row.map(csvCell).join(",")).join("\n");
}

function csvCell(value: string) {
  return `"${value.replace(/"/g, '""')}"`;
}

function slugify(value: string) {
  return value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

type IncidentsChartProps = {
  values: number[];
};

type FilterOptionButtonProps = {
  iconName: keyof typeof Ionicons.glyphMap;
  label: string;
  onPress: () => void;
  selected: boolean;
};

type GradientTitleProps = {
  fontFamily?: string;
  fontSize: number;
  height: number;
  style: object;
  text: string;
  width: number;
  y: number;
};

function FilterOptionButton({
  iconName,
  label,
  onPress,
  selected,
}: FilterOptionButtonProps) {
  const content = (
    <>
      <Ionicons
        color={selected ? INSIGHTS_COLORS.gradientMiddle : "#000000"}
        name={iconName}
        size={20}
      />
      <Text style={[styles.filterOptionText, selected && styles.filterOptionTextActive]}>
        {label}
      </Text>
    </>
  );

  if (selected) {
    return (
      <ExpoLinearGradient
        colors={INSIGHTS_GRADIENT_COLORS}
        locations={INSIGHTS_GRADIENT_LOCATIONS}
        style={styles.filterOptionGradientBorder}
      >
        <Pressable
          accessibilityRole="button"
          onPress={onPress}
          style={({ pressed }) => [
            styles.filterOptionCardGradient,
            styles.filterOptionCardGradientSelected,
            pressed && styles.pressed,
          ]}
        >
          {content}
        </Pressable>
      </ExpoLinearGradient>
    );
  }

  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [styles.filterOptionCard, pressed && styles.pressed]}
    >
      {content}
    </Pressable>
  );
}

function GradientTitle({
  fontFamily = INSIGHTS_FONTS.extraBold,
  fontSize,
  height,
  style,
  text,
  width,
  y,
}: GradientTitleProps) {
  const gradientId = `${text}TitleGradient`;

  return (
    <Svg height={height} style={style} viewBox={`0 0 ${width} ${height}`} width={width}>
      <Defs>
        <LinearGradient id={gradientId} x1="0" x2="1" y1="0" y2="0">
          <Stop offset="8%" stopColor={INSIGHTS_COLORS.gradientStart} />
          <Stop offset="38%" stopColor={INSIGHTS_COLORS.gradientMiddle} />
          <Stop offset="100%" stopColor={INSIGHTS_COLORS.gradientEnd} />
        </LinearGradient>
      </Defs>
      <SvgText
        fill={`url(#${gradientId})`}
        fontFamily={fontFamily}
        fontSize={fontSize}
        x={0}
        y={y}
      >
        {text}
      </SvgText>
    </Svg>
  );
}

function IncidentsChart({ values }: IncidentsChartProps) {
  const width = 294;
  const height = 192;
  const chartTop = 28;
  const chartLeft = 24;
  const plotWidth = 270;
  const plotHeight = 120;
  const min = 0;
  const max = Math.max(5, ...values);
  const ticks = [max, max * 0.75, max * 0.5, max * 0.25, min];
  const labels = ["03", "06", "09", "12", "15", "18", "20", "23"];

  const points = values.map((value, index) => {
    const x = chartLeft + (index / (values.length - 1)) * plotWidth;
    const y = chartTop + plotHeight - ((value - min) / (max - min)) * plotHeight;
    return { x, y };
  });

  const path = points
    .map((point, index) => {
      if (index === 0) {
        return `M ${point.x} ${point.y}`;
      }

      const previous = points[index - 1];
      const controlX = (previous.x + point.x) / 2;
      return `C ${controlX} ${previous.y}, ${controlX} ${point.y}, ${point.x} ${point.y}`;
    })
    .join(" ");

  const areaPath = `${path} L ${points[points.length - 1].x} ${chartTop + plotHeight} L ${points[0].x} ${chartTop + plotHeight} Z`;

  return (
    <View style={styles.chartContainer}>
      <Svg height={height} viewBox={`0 0 ${width} ${height}`} width="100%">
        <Defs>
          <LinearGradient id="chartFill" x1="0" x2="0" y1="0" y2="1">
            <Stop
              offset="8%"
              stopColor={INSIGHTS_COLORS.gradientStart}
              stopOpacity="0.28"
            />
            <Stop
              offset="38%"
              stopColor={INSIGHTS_COLORS.gradientMiddle}
              stopOpacity="0.16"
            />
            <Stop
              offset="100%"
              stopColor={INSIGHTS_COLORS.gradientEnd}
              stopOpacity="0"
            />
          </LinearGradient>
          <LinearGradient id="chartLineGradient" x1="0" x2="1" y1="0" y2="0">
            <Stop offset="8%" stopColor={INSIGHTS_COLORS.gradientStart} />
            <Stop offset="38%" stopColor={INSIGHTS_COLORS.gradientMiddle} />
            <Stop offset="100%" stopColor={INSIGHTS_COLORS.gradientEnd} />
          </LinearGradient>
        </Defs>

        {ticks.map((tick) => {
          const y = chartTop + plotHeight - ((tick - min) / (max - min)) * plotHeight;

          return (
            <G key={tick}>
              <SvgText
                fill="#92A0B6"
                fontFamily={INSIGHTS_FONTS.medium}
                fontSize={12}
                fontWeight="500"
                textAnchor="start"
                x={0}
                y={y + 4}
              >
                {String(Math.round(tick)).padStart(2, "0")}
              </SvgText>
              <Line
                stroke="#EEF3F8"
                strokeWidth={1}
                x1={chartLeft}
                x2={width}
                y1={y}
                y2={y}
              />
            </G>
          );
        })}

        <Path d={areaPath} fill="url(#chartFill)" />
        <Path
          d={path}
          fill="none"
          stroke="url(#chartLineGradient)"
          strokeLinecap="round"
          strokeWidth={2.5}
        />

        {points.slice(1, -1).map((point, index) => (
          <Circle
            cx={point.x}
            cy={point.y}
            fill={INSIGHTS_COLORS.gradientMiddle}
            key={`${point.x}-${index}`}
            r={4}
          />
        ))}

        <Line
          stroke="#E7EEF5"
          strokeWidth={1}
          x1={chartLeft}
          x2={width}
          y1={chartTop + plotHeight}
          y2={chartTop + plotHeight}
        />

        {labels.map((label, index) => {
          const x = chartLeft + (index / (labels.length - 1)) * plotWidth;

          return (
            <SvgText
              fill="#92A0B6"
              fontFamily={INSIGHTS_FONTS.medium}
              fontSize={12}
              fontWeight="500"
              key={label}
              textAnchor="middle"
              x={x}
              y={height - 10}
            >
              {label}
            </SvgText>
          );
        })}

        <Rect fill="transparent" height={height} width={width} x={0} y={0} />
      </Svg>
    </View>
  );
}
