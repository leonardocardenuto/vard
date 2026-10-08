import { Ionicons } from "@expo/vector-icons";
import * as FileSystem from "expo-file-system/legacy";
import * as Print from "expo-print";
import * as Sharing from "expo-sharing";
import { RouteProp, useRoute } from "@react-navigation/native";
import { useFonts } from "expo-font";
import { LinearGradient as ExpoLinearGradient } from "expo-linear-gradient";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Animated,
  Modal,
  PanResponder,
  Platform,
  Pressable,
  RefreshControl,
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
  FallEventResponse,
  NotificationResponse,
  WorkspaceResponse,
  listFallEvents,
  listCameras,
  listNotifications,
  listWorkspaces,
  updateNotification,
} from "../../../lib/api";
import { AppTabParamList } from "../../../navigation/types";
import {
  INSIGHTS_COLORS,
  INSIGHTS_FONTS,
  INSIGHTS_GRADIENT_COLORS,
  INSIGHTS_GRADIENT_LOCATIONS,
  styles,
} from "../styles/Insights";

type Period = "Últimos 15 dias" | "Últimos 30 dias" | "Últimos 60 dias" | "Últimos 90 dias";
type CameraFilter = string;
type InsightsRoute = RouteProp<AppTabParamList, "Insights">;
type IncidentStatus = "new" | "confirmed" | "false_positive" | "resolved";

type CameraData = {
  availabilityCameraName: string;
  availabilityMessage: string;
  availabilitySegments: AvailabilitySegment[];
  availabilityStatusLabel: string;
  dailyIncidentMessage: string;
  dailyIncidentTotal: number;
  falsePositiveTotal: number;
  incidentDetails: IncidentDetail[];
  incidentSeries: IncidentSeriesPoint[];
  incidentTotal: number;
  roomIncidents: Array<{
    isEmpty?: boolean;
    room: string;
    value: number;
    barStyle: object;
  }>;
};

type IncidentSeriesPoint = {
  label: string;
  value: number;
};

type ActivitySegment = {
  left: `${number}%`;
  width: `${number}%`;
};

type AvailabilitySegment = ActivitySegment & {
  status: "offline" | "online";
};

type IncidentDetail = {
  body: string;
  cameraName: string;
  dateLabel: string;
  hasClip: boolean;
  id: string;
  notification: NotificationResponse;
  probabilityLabel: string;
  room: string;
  severity: NotificationResponse["severity"];
  status: IncidentStatus;
  statusLabel: string;
  timeLabel: string;
  title: string;
};

const PERIOD_OPTIONS: Period[] = [
  "Últimos 15 dias",
  "Últimos 30 dias",
  "Últimos 60 dias",
  "Últimos 90 dias",
];

const DEFAULT_PERIOD: Period = "Últimos 90 dias";
const ALL_CAMERAS_FILTER = "Todas";
const ALL_WORKSPACES_ID = "__all_workspaces__";

const PERIOD_DAYS: Record<Period, number> = {
  "Últimos 15 dias": 15,
  "Últimos 30 dias": 30,
  "Últimos 60 dias": 60,
  "Últimos 90 dias": 90,
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
  const [selectedAvailabilityCameraId, setSelectedAvailabilityCameraId] = useState<string | null>(null);
  const [fallEvents, setFallEvents] = useState<FallEventResponse[]>([]);
  const [notifications, setNotifications] = useState<NotificationResponse[]>([]);
  const [isLoadingInsights, setIsLoadingInsights] = useState(true);
  const [isRefreshingInsights, setIsRefreshingInsights] = useState(false);
  const [insightsError, setInsightsError] = useState("");
  const [exportLabel, setExportLabel] = useState("Exportar relatório PDF");
  const [updatingIncidentId, setUpdatingIncidentId] = useState<string | null>(null);
  const sheetAnimation = useRef(new Animated.Value(0)).current;
  const sheetDragY = useRef(new Animated.Value(0)).current;

  const effectivePeriod = period ?? DEFAULT_PERIOD;
  const effectiveCamera = selectedCamera ?? ALL_CAMERAS_FILTER;
  const isAllWorkspacesSelected = selectedWorkspaceId === ALL_WORKSPACES_ID;
  const selectedWorkspace = useMemo(
    () =>
      isAllWorkspacesSelected
        ? null
        : workspaces.find((workspace) => workspace.id === selectedWorkspaceId) ?? workspaces[0] ?? null,
    [isAllWorkspacesSelected, selectedWorkspaceId, workspaces],
  );
  const workspaceNamesById = useMemo(
    () => new Map(workspaces.map((workspace) => [workspace.id, workspace.name])),
    [workspaces],
  );
  const selectedWorkspaceLabel = isAllWorkspacesSelected
    ? "Todos os workspaces"
    : selectedWorkspace?.name ?? "Selecione";
  const selectedWorkspaceGroup = useMemo(
    () =>
      isAllWorkspacesSelected
        ? workspaces
        : selectedWorkspace
          ? [selectedWorkspace]
          : [],
    [isAllWorkspacesSelected, selectedWorkspace, workspaces],
  );
  const cameraOptions = useMemo(
    () => [ALL_CAMERAS_FILTER, ...cameras.map((camera) => camera.name)],
    [cameras],
  );
  const selectedData = useMemo(
    () => buildInsightsData({
      cameras,
      cameraName: effectiveCamera,
      fallEvents,
      notifications,
      period: effectivePeriod,
      selectedAvailabilityCameraId,
      workspaceNamesById,
    }),
    [
      cameras,
      effectiveCamera,
      effectivePeriod,
      fallEvents,
      notifications,
      selectedAvailabilityCameraId,
      workspaceNamesById,
    ],
  );

  const loadWorkspaces = useCallback(async () => {
    if (!accessToken) {
      setInsightsError("Sessão inválida. Faça login novamente.");
      setIsLoadingInsights(false);
      return;
    }

    try {
      setInsightsError("");
      setIsLoadingInsights(true);
      const workspaceList = await listWorkspaces(accessToken);
      setWorkspaces(workspaceList);
      setSelectedWorkspaceId((current) => current ?? ALL_WORKSPACES_ID);
    } catch (error) {
      setInsightsError(
        error instanceof ApiRequestError ? error.message : "Não foi possível carregar os workspaces."
      );
      setIsLoadingInsights(false);
    }
  }, [accessToken]);

  const loadWorkspaceInsights = useCallback(async () => {
    if (!accessToken || selectedWorkspaceGroup.length === 0) {
      setCameras([]);
      setSelectedAvailabilityCameraId(null);
      setFallEvents([]);
      setNotifications([]);
      setIsLoadingInsights(false);
      return;
    }

    try {
      setInsightsError("");
      setIsLoadingInsights(true);
      const workspaceResults = await Promise.all(
        selectedWorkspaceGroup.map(async (workspace) => {
          const [workspaceCameras, workspaceNotifications, workspaceFallEvents] = await Promise.all([
            listCameras(accessToken, workspace.id),
            listNotifications(accessToken, workspace.id),
            listFallEvents(accessToken, workspace.id),
          ]);

          return { workspaceCameras, workspaceNotifications, workspaceFallEvents };
        }),
      );
      const workspaceCameras = workspaceResults.flatMap((result) => result.workspaceCameras);
      const workspaceNotifications = workspaceResults.flatMap((result) => result.workspaceNotifications);
      const workspaceFallEvents = workspaceResults.flatMap((result) => result.workspaceFallEvents);
      setCameras(workspaceCameras);
      setFallEvents(workspaceFallEvents);
      setNotifications(workspaceNotifications);
      setSelectedAvailabilityCameraId((current) =>
        current && workspaceCameras.some((camera) => camera.id === current)
          ? current
          : workspaceCameras[0]?.id ?? null,
      );
      setSelectedCamera((current) => {
        if (!current || current === ALL_CAMERAS_FILTER) {
          return current;
        }
        return workspaceCameras.some((camera) => camera.name === current) ? current : null;
      });
    } catch (error) {
      setInsightsError(
        error instanceof ApiRequestError ? error.message : "Não foi possível carregar os insights."
      );
    } finally {
      setIsLoadingInsights(false);
    }
  }, [accessToken, selectedWorkspaceGroup]);

  useEffect(() => {
    void loadWorkspaces();
  }, [loadWorkspaces]);

  useEffect(() => {
    void loadWorkspaceInsights();
  }, [loadWorkspaceInsights]);

  const handleRefresh = useCallback(async () => {
    setIsRefreshingInsights(true);
    try {
      await loadWorkspaces();
      await loadWorkspaceInsights();
    } finally {
      setIsRefreshingInsights(false);
    }
  }, [loadWorkspaceInsights, loadWorkspaces]);

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

  async function handleExportReport() {
    const reportNotifications = filterNotificationsBySelection({
      cameras,
      cameraName: effectiveCamera,
      notifications,
      period: effectivePeriod,
    });
    const html = buildPdfReportHtml({
      cameraName: effectiveCamera,
      cameras,
      data: selectedData,
      notifications: reportNotifications,
      period: effectivePeriod,
      workspaceName: selectedWorkspaceLabel,
      workspaceNamesById,
    });
    const fileName = `vard-insights-${slugify(selectedWorkspaceLabel)}-${Date.now()}.pdf`;

    try {
      const generated = await Print.printToFileAsync({ html, base64: true });
      let fileUri = generated.uri;
      let savedInFilesApp = false;

      if (Platform.OS === "android" && generated.base64) {
        const directoryPermission = await FileSystem.StorageAccessFramework.requestDirectoryPermissionsAsync();
        if (!directoryPermission.granted) {
          setExportLabel("Exportar relatório PDF");
          Alert.alert(
            "Exportação cancelada",
            "Escolha uma pasta, como Downloads ou Documentos, para salvar o PDF e vê-lo no app Files.",
          );
          return;
        }

        fileUri = await FileSystem.StorageAccessFramework.createFileAsync(
          directoryPermission.directoryUri,
          fileName,
          "application/pdf",
        );
        await FileSystem.writeAsStringAsync(fileUri, generated.base64, {
          encoding: FileSystem.EncodingType.Base64,
        });
        savedInFilesApp = true;
      } else if (generated.base64 && FileSystem.documentDirectory) {
        fileUri = `${FileSystem.documentDirectory}${fileName}`;
        await FileSystem.writeAsStringAsync(fileUri, generated.base64, {
          encoding: FileSystem.EncodingType.Base64,
        });
      }

      setExportLabel("Relatório exportado");

      const canShare = Platform.OS !== "web" && await Sharing.isAvailableAsync();
      Alert.alert(
        "Relatório exportado",
        savedInFilesApp
          ? `PDF salvo na pasta escolhida: ${fileName}\nQuedas: ${selectedData.incidentTotal}`
          : `PDF gerado: ${fileName}\nQuedas: ${selectedData.incidentTotal}`,
        [
          { text: "OK" },
          ...(canShare
            ? [{
                text: "Compartilhar",
                onPress: () => void Sharing.shareAsync(fileUri, {
                  dialogTitle: "Compartilhar relatório VARD",
                  mimeType: "application/pdf",
                  UTI: "com.adobe.pdf",
                }),
              }]
            : []),
        ],
      );
    } catch {
      setExportLabel("Exportar relatório PDF");
      Alert.alert("Falha ao exportar", "Não foi possível gerar o PDF.");
    }
  }

  async function handleIncidentStatusUpdate(
    incident: IncidentDetail,
    status: IncidentStatus,
  ) {
    if (!accessToken || updatingIncidentId) {
      return;
    }

    setUpdatingIncidentId(incident.id);
    try {
      const now = new Date().toISOString();
      const updatedNotification = await updateNotification(accessToken, incident.id, {
        payload: {
          ...incident.notification.payload,
          detection_validation: {
            answered_at: now,
            is_valid: status !== "false_positive",
          },
          incident_resolution: {
            status,
            updated_at: now,
            updated_by: "insights",
          },
        },
      });
      setNotifications((currentNotifications) =>
        currentNotifications.map((notification) =>
          notification.id === updatedNotification.id ? updatedNotification : notification,
        ),
      );
    } catch (error) {
      Alert.alert(
        "Não foi possível atualizar",
        error instanceof ApiRequestError ? error.message : "Tente novamente em instantes.",
      );
    } finally {
      setUpdatingIncidentId(null);
    }
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
          refreshControl={
            <RefreshControl
              colors={[INSIGHTS_COLORS.gradientMiddle]}
              onRefresh={handleRefresh}
              refreshing={isRefreshingInsights}
              tintColor={INSIGHTS_COLORS.gradientMiddle}
            />
          }
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
                      {selectedWorkspaceLabel}
                    </Text>
                    <Ionicons
                      color={INSIGHTS_COLORS.gradientMiddle}
                      name={isWorkspaceMenuOpen ? "chevron-up" : "chevron-down"}
                      size={18}
                    />
                  </Pressable>

                  {isWorkspaceMenuOpen ? (
                    <View style={styles.workspaceMenu}>
                      <Pressable
                        accessibilityRole="button"
                        onPress={() => handleWorkspaceSelect(ALL_WORKSPACES_ID)}
                        style={({ pressed }) => [
                          styles.workspaceMenuItem,
                          isAllWorkspacesSelected && styles.workspaceMenuItemSelected,
                          pressed && styles.pressed,
                        ]}
                      >
                        <Text
                          numberOfLines={1}
                          style={[
                            styles.workspaceMenuItemText,
                            isAllWorkspacesSelected && styles.workspaceMenuItemTextSelected,
                          ]}
                        >
                          Todos os workspaces
                        </Text>
                        {isAllWorkspacesSelected ? (
                          <Ionicons
                            color={INSIGHTS_COLORS.gradientMiddle}
                            name="checkmark"
                            size={16}
                          />
                        ) : null}
                      </Pressable>
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
                Resumo de atividades e saúde do dia.
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
                  <Text style={styles.cardTitle}>Quedas</Text>
                  <Text style={styles.cardSubtitle}>Quedas x dias</Text>
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

              <IncidentsChart series={selectedData.incidentSeries} />
            </View>

            <View style={styles.metricsGrid}>
              <MetricCard
                label="Total no período"
                value={String(selectedData.incidentTotal)}
              />
              <MetricCard
                label="Últimas 24h"
                value={String(selectedData.dailyIncidentTotal)}
              />
              <MetricCard
                label="Falsas detecções"
                value={String(selectedData.falsePositiveTotal)}
              />
            </View>

            <View style={styles.cardRooms}>
              <Text style={styles.roomsTitle}>Quedas por cômodo</Text>
              <View style={styles.roomList}>
                {selectedData.roomIncidents.map((item) => (
                  <View key={item.room} style={styles.roomItem}>
                    <View style={styles.roomTopLine}>
                      <Text style={[styles.roomName, item.isEmpty && styles.roomNameMuted]}>
                        {item.room}
                      </Text>
                      <Text style={styles.roomValue}>{item.value}</Text>
                    </View>
                    {item.isEmpty ? null : (
                      <View style={styles.roomTrack}>
                        <View style={[styles.roomBar, item.barStyle]} />
                      </View>
                    )}
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
              <Text style={styles.dailyLabel}>INCIDENTES NAS ÚLTIMAS 24H</Text>
              <Text style={styles.dailyValue}>
                {selectedData.dailyIncidentTotal}
              </Text>
              <Text style={styles.dailyText}>
                {selectedData.dailyIncidentMessage}
              </Text>
            </View>

            <View style={styles.incidentHistoryCard}>
              <View style={styles.incidentHistoryHeader}>
                <View>
                  <Text style={styles.roomsTitle}>Histórico de quedas</Text>
                  <Text style={styles.cardSubtitle}>
                    Confirme ou marque falsas detecções.
                  </Text>
                </View>
              </View>

              {selectedData.incidentDetails.length === 0 ? (
                <View style={styles.emptyIncidentHistory}>
                  <Ionicons
                    color="#92A0B6"
                    name="checkmark-circle-outline"
                    size={28}
                  />
                  <Text style={styles.emptyIncidentHistoryText}>
                    Nenhuma queda no período selecionado.
                  </Text>
                </View>
              ) : null}

              <View style={styles.incidentList}>
                {selectedData.incidentDetails.map((incident) => (
                  <View key={incident.id} style={styles.incidentItem}>
                    <View style={styles.incidentItemHeader}>
                      <View style={styles.incidentIconWrap}>
                        <Ionicons
                          color="#CA171B"
                          name="alert-circle-outline"
                          size={21}
                        />
                      </View>
                      <View style={styles.incidentTitleWrap}>
                        <Text numberOfLines={1} style={styles.incidentTitle}>
                          {incident.room}
                        </Text>
                        <Text numberOfLines={1} style={styles.incidentMeta}>
                          {incident.dateLabel} às {incident.timeLabel} • {incident.cameraName}
                        </Text>
                      </View>
                      <Text
                        style={[
                          styles.incidentStatusBadge,
                          incident.status === "confirmed" && styles.incidentStatusDanger,
                          incident.status === "resolved" && styles.incidentStatusSuccess,
                          incident.status === "false_positive" && styles.incidentStatusMuted,
                        ]}
                      >
                        {incident.statusLabel}
                      </Text>
                    </View>

                    <View style={styles.incidentFacts}>
                      <Text style={styles.incidentFact}>
                        Prob.: {incident.probabilityLabel}
                      </Text>
                      <Text style={styles.incidentFact}>
                        Clipe: {incident.hasClip ? "sim" : "não"}
                      </Text>
                      <Text style={styles.incidentFact}>
                        Severidade: {incident.severity}
                      </Text>
                    </View>

                    <View style={styles.incidentActions}>
                      <IncidentActionButton
                        disabled={updatingIncidentId === incident.id}
                        label="Confirmar"
                        onPress={() => void handleIncidentStatusUpdate(incident, "confirmed")}
                        selected={incident.status === "confirmed"}
                      />
                      <IncidentActionButton
                        disabled={updatingIncidentId === incident.id}
                        label="Falsa detecção"
                        onPress={() => void handleIncidentStatusUpdate(incident, "false_positive")}
                        selected={incident.status === "false_positive"}
                      />
                    </View>
                  </View>
                ))}
              </View>
            </View>

            <GradientTitle
              fontFamily={INSIGHTS_FONTS.semiBold}
              fontSize={40}
              height={52}
              style={styles.activityTitle}
              text="Horários"
              width={200}
              y={39}
            />

            <View style={styles.activityCard}>
              <Text style={styles.cameraTitle}>
                {selectedData.availabilityCameraName}
              </Text>
              <Text style={styles.cameraSubtitle}>
                {selectedData.availabilityStatusLabel}
              </Text>
              <ScrollView
                contentContainerStyle={styles.availabilityFilterContent}
                horizontal
                showsHorizontalScrollIndicator={false}
                style={styles.availabilityFilter}
              >
                {cameras.length === 0 ? (
                  <Text style={styles.availabilityEmptyText}>
                    Nenhuma câmera cadastrada
                  </Text>
                ) : null}
                {cameras.map((camera) => {
                  const selected = camera.id === selectedAvailabilityCameraId;
                  const label = isAllWorkspacesSelected
                    ? `${workspaceNamesById.get(camera.workspace_id) ?? "Workspace"} • ${camera.name}`
                    : camera.name;
                  return (
                    <Pressable
                      accessibilityRole="button"
                      key={camera.id}
                      onPress={() => setSelectedAvailabilityCameraId(camera.id)}
                      style={({ pressed }) => [
                        styles.availabilityCameraChip,
                        selected && styles.availabilityCameraChipSelected,
                        pressed && styles.pressed,
                      ]}
                    >
                      <Text
                        numberOfLines={1}
                        style={[
                          styles.availabilityCameraChipText,
                          selected && styles.availabilityCameraChipTextSelected,
                        ]}
                      >
                        {label}
                      </Text>
                    </Pressable>
                  );
                })}
              </ScrollView>
              <View style={styles.activityChart}>
                <View style={styles.activityTrack}>
                  {selectedData.availabilitySegments.map((segment, index) => (
                    <View
                      key={index}
                      style={[
                        styles.activitySegment,
                        segment.status === "offline" && styles.activitySegmentOffline,
                        { left: segment.left, width: segment.width },
                      ]}
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
                  <Text style={styles.legendText}>Disponível</Text>
                </View>
                <View style={styles.legendRow}>
                  <View style={styles.legendOfflineDot} />
                  <Text style={styles.legendText}>Fora do ar</Text>
                </View>
              </View>
              <Text style={styles.availabilityNote}>
                {selectedData.availabilityMessage}
              </Text>
            </View>

            <Pressable
              accessibilityLabel="Exportar relatório mensal em PDF"
              accessibilityRole="button"
              onPress={() => void handleExportReport()}
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
  fallEvents,
  notifications,
  period,
  selectedAvailabilityCameraId,
  workspaceNamesById,
}: {
  cameras: CameraResponse[];
  cameraName: string;
  fallEvents: FallEventResponse[];
  notifications: NotificationResponse[];
  period: Period;
  selectedAvailabilityCameraId: string | null;
  workspaceNamesById: Map<string, string>;
}): CameraData {
  const { filteredNotifications, now, startTime } = filterNotificationsBySelection({
    cameras,
    cameraName,
    notifications,
    period,
    withBounds: true,
  });
  const camerasById = new Map(cameras.map((camera) => [camera.id, camera]));
  const fallEventsByNotificationId = new Map(
    fallEvents
      .filter((event) => event.notification_id)
      .map((event) => [event.notification_id as string, event]),
  );
  const availabilityCamera =
    cameras.find((camera) => camera.id === selectedAvailabilityCameraId) ?? cameras[0];
  const availabilitySegments = buildAvailabilitySegments({
    camera: availabilityCamera,
    endTime: now,
    notifications,
  });
  const countableNotifications = filteredNotifications.filter(
    (notification) => getIncidentStatus(notification) !== "false_positive",
  );
  const last24HoursStart = now - 24 * 60 * 60 * 1000;
  const dailyIncidentTotal = countableNotifications.filter((notification) => {
    const createdAt = new Date(notification.created_at).getTime();
    return Number.isFinite(createdAt) && createdAt >= last24HoursStart;
  }).length;

  const roomCounts = new Map<string, number>();
  countableNotifications.forEach((notification) => {
    const camera = notification.camera_id ? camerasById.get(notification.camera_id) : undefined;
    const workspaceName = workspaceNamesById.get(notification.workspace_id) ?? "Workspace";
    const room = `${workspaceName} • ${resolveNotificationRoom(notification, camera)}`;
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
    availabilityCameraName: availabilityCamera
      ? `${workspaceNamesById.get(availabilityCamera.workspace_id) ?? "Workspace"} • ${availabilityCamera.name}`
      : "Câmeras",
    availabilityMessage: buildAvailabilityMessage(availabilityCamera, availabilitySegments),
    availabilitySegments,
    availabilityStatusLabel: availabilityCamera
      ? `Status atual: ${availabilityCamera.status.toLowerCase() === "online" ? "online" : "fora do ar"}`
      : "Cadastre uma câmera para visualizar disponibilidade.",
    dailyIncidentMessage:
      dailyIncidentTotal > 0
        ? `${dailyIncidentTotal} queda${dailyIncidentTotal === 1 ? "" : "s"} detectada${dailyIncidentTotal === 1 ? "" : "s"} nas últimas 24 horas.`
        : "Nenhuma queda detectada nas últimas 24 horas.",
    dailyIncidentTotal,
    falsePositiveTotal: filteredNotifications.length - countableNotifications.length,
    incidentDetails: filteredNotifications
      .slice()
      .sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      )
      .slice(0, 12)
      .map((notification) => {
        const camera = notification.camera_id ? camerasById.get(notification.camera_id) : undefined;
        const status = getIncidentStatus(notification);
        const event = fallEventsByNotificationId.get(notification.id);
        return {
          body: notification.body,
          cameraName: camera?.name ?? "Sem câmera",
          dateLabel: formatIncidentDate(notification.created_at),
          hasClip: event?.has_clip ?? false,
          id: notification.id,
          notification,
          probabilityLabel: formatProbabilityLabel(notification),
          room: resolveNotificationRoom(notification, camera),
          severity: notification.severity,
          status,
          statusLabel: getIncidentStatusLabel(status),
          timeLabel: formatIncidentTime(notification.created_at),
          title: notification.title,
        };
      }),
    incidentSeries: buildIncidentSeries(countableNotifications, startTime, now),
    incidentTotal: countableNotifications.length,
    roomIncidents:
      roomIncidents.length > 0
        ? roomIncidents
        : [{ room: "Sem quedas no período", value: 0, barStyle: { width: "0%" }, isEmpty: true }],
  };
}

function buildIncidentSeries(
  notifications: NotificationResponse[],
  startTime: number,
  endTime: number,
): IncidentSeriesPoint[] {
  const bucketCount = 8;
  const bucketSize = Math.max(1, (endTime - startTime) / bucketCount);
  const series = Array.from({ length: bucketCount }, (_, index) => ({
    label: formatChartDateLabel(startTime + bucketSize * index),
    value: 0,
  }));

  notifications.forEach((notification) => {
    const createdAt = new Date(notification.created_at).getTime();
    if (!Number.isFinite(createdAt)) {
      return;
    }

    const bucketIndex = Math.min(
      bucketCount - 1,
      Math.max(0, Math.floor((createdAt - startTime) / bucketSize)),
    );
    series[bucketIndex].value += 1;
  });

  return series;
}

function buildAvailabilitySegments({
  camera,
  endTime,
  notifications,
}: {
  camera?: CameraResponse;
  endTime: number;
  notifications: NotificationResponse[];
}): AvailabilitySegment[] {
  if (!camera) {
    return [];
  }

  const startTime = endTime - 24 * 60 * 60 * 1000;
  const bucketCount = 24;
  const bucketSize = (endTime - startTime) / bucketCount;
  const currentCameraStatus = camera.status.toLowerCase();
  const initialStatus: "offline" | "online" =
    currentCameraStatus === "online" ? "online" : "offline";
  const bucketStatuses = Array.from({ length: bucketCount }, () => initialStatus);
  const lastSeenAt = camera.last_seen_at ? new Date(camera.last_seen_at).getTime() : NaN;

  if (currentCameraStatus !== "online" && Number.isFinite(lastSeenAt) && lastSeenAt > startTime) {
    bucketStatuses.forEach((_, index) => {
      const bucketStart = startTime + index * bucketSize;
      bucketStatuses[index] = bucketStart <= lastSeenAt ? "online" : "offline";
    });
  }

  notifications
    .filter((notification) => notification.camera_id === camera.id)
    .map((notification) => ({
      createdAt: new Date(notification.created_at).getTime(),
      status: resolveAvailabilityEventStatus(notification),
    }))
    .filter(
      (event): event is { createdAt: number; status: "offline" | "online" } =>
        Number.isFinite(event.createdAt) &&
        event.createdAt >= startTime &&
        event.createdAt <= endTime &&
        event.status !== null,
    )
    .sort((a, b) => a.createdAt - b.createdAt)
    .forEach((event) => {
      const startBucket = Math.min(
        bucketCount - 1,
        Math.max(0, Math.floor((event.createdAt - startTime) / bucketSize)),
      );
      for (let index = startBucket; index < bucketCount; index += 1) {
        bucketStatuses[index] = event.status;
      }
    });

  const segments: AvailabilitySegment[] = [];
  let segmentStart = 0;
  let currentStatus = bucketStatuses[0];

  bucketStatuses.forEach((status, index) => {
    const isLastBucket = index === bucketStatuses.length - 1;
    if (status !== currentStatus || isLastBucket) {
      const segmentEnd = status !== currentStatus ? index : index + 1;
      segments.push({
        left: `${Math.round((segmentStart / bucketCount) * 100)}` as `${number}%`,
        status: currentStatus,
        width: `${Math.max(4, Math.round(((segmentEnd - segmentStart) / bucketCount) * 100))}` as `${number}%`,
      });
      segmentStart = index;
      currentStatus = status;
    }
  });

  return segments;
}

function resolveAvailabilityEventStatus(notification: NotificationResponse) {
  const searchableText = `${notification.notification_type} ${notification.title} ${notification.body}`.toLowerCase();
  if (
    searchableText.includes("offline") ||
    searchableText.includes("desconect") ||
    searchableText.includes("fora do ar")
  ) {
    return "offline" as const;
  }

  if (
    searchableText.includes("online") ||
    searchableText.includes("conectada") ||
    searchableText.includes("disponivel") ||
    searchableText.includes("disponível")
  ) {
    return "online" as const;
  }

  return null;
}

function buildAvailabilityMessage(
  camera: CameraResponse | undefined,
  segments: AvailabilitySegment[],
) {
  if (!camera) {
    return "Sem câmera selecionada para calcular disponibilidade.";
  }

  const offlineSegments = segments.filter((segment) => segment.status === "offline");
  if (offlineSegments.length === 0) {
    return "Sem períodos fora do ar identificados nas últimas 24 horas.";
  }

  return `${offlineSegments.length} período${offlineSegments.length === 1 ? "" : "s"} fora do ar nas últimas 24 horas.`;
}

function isFallNotification(notification: NotificationResponse) {
  const searchableText = `${notification.notification_type} ${notification.title}`.toLowerCase();
  return searchableText.includes("fall") || searchableText.includes("queda");
}

function getIncidentStatus(notification: NotificationResponse): IncidentStatus {
  const resolution = notification.payload?.incident_resolution;
  if (resolution && typeof resolution === "object") {
    const status = (resolution as Record<string, unknown>).status;
    if (
      status === "confirmed" ||
      status === "false_positive" ||
      status === "resolved"
    ) {
      return status;
    }
  }

  const validation = notification.payload?.detection_validation;
  if (validation && typeof validation === "object") {
    const isValid = (validation as Record<string, unknown>).is_valid;
    if (isValid === false) {
      return "false_positive";
    }
    if (isValid === true) {
      return "confirmed";
    }
  }

  return "new";
}

function getIncidentStatusLabel(status: IncidentStatus) {
  const labels: Record<IncidentStatus, string> = {
    confirmed: "Confirmada",
    false_positive: "Falsa detecção",
    new: "Nova",
    resolved: "Resolvida",
  };
  return labels[status];
}

function formatProbabilityLabel(notification: NotificationResponse) {
  const probability = numberFromPayload(notification.payload ?? {}, [
    "fall_probability",
    "probability",
    "confidence",
    "precision",
  ]);
  if (probability === null) {
    return "--";
  }
  const percentage = probability <= 1 ? probability * 100 : probability;
  return `${Math.round(percentage)}%`;
}

function formatIncidentDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "--/--";
  }
  return date.toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
  });
}

function formatIncidentTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "--:--";
  }
  return date.toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function numberFromPayload(payload: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = payload[key];
    if (typeof value === "number") {
      return value;
    }
    if (
      typeof value === "string" &&
      value.trim() &&
      !Number.isNaN(Number(value))
    ) {
      return Number(value);
    }
  }
  return null;
}

function resolveNotificationRoom(
  notification: NotificationResponse,
  camera?: CameraResponse,
) {
  const payloadRoom = notification.payload?.room;
  const metadata = camera?.metadata_json ?? camera?.metadata;
  const metadataRoom = metadata?.room;

  if (typeof payloadRoom === "string" && payloadRoom.trim()) {
    return payloadRoom.trim();
  }

  if (typeof metadataRoom === "string" && metadataRoom.trim()) {
    return metadataRoom.trim();
  }

  return camera?.name ?? notification.notification_type;
}

function formatChartDateLabel(timestamp: number) {
  return new Date(timestamp).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
  });
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

    return isFallNotification(notification) && isInsidePeriod && matchesCamera;
  });

  if (withBounds) {
    return { filteredNotifications, now, startTime };
  }

  return filteredNotifications;
}

function buildPdfReportHtml({
  cameraName,
  cameras,
  data,
  notifications,
  period,
  workspaceName,
  workspaceNamesById,
}: {
  cameraName: string;
  cameras: CameraResponse[];
  data: CameraData;
  notifications: NotificationResponse[];
  period: Period;
  workspaceName: string;
  workspaceNamesById: Map<string, string>;
}) {
  const camerasById = new Map(cameras.map((camera) => [camera.id, camera]));
  const generatedAt = new Date().toLocaleString("pt-BR");
  const incidentRows = notifications.length > 0
    ? notifications.map((notification) => {
        const camera = notification.camera_id ? camerasById.get(notification.camera_id) : undefined;
        return `
          <tr>
            <td>${escapeHtml(new Date(notification.created_at).toLocaleString("pt-BR"))}</td>
            <td>${escapeHtml(workspaceNamesById.get(notification.workspace_id) ?? "Workspace")}</td>
            <td>${escapeHtml(camera?.name ?? "Sem câmera")}</td>
            <td>${escapeHtml(resolveNotificationRoom(notification, camera))}</td>
            <td>${escapeHtml(getIncidentStatusLabel(getIncidentStatus(notification)))}</td>
            <td>${escapeHtml(formatProbabilityLabel(notification))}</td>
            <td>${escapeHtml(notification.severity)}</td>
            <td>${escapeHtml(notification.title)}</td>
          </tr>
        `;
      }).join("")
    : `<tr><td colspan="8">Nenhuma queda no período selecionado.</td></tr>`;
  const roomRows = data.roomIncidents.map((item) => `
    <tr>
      <td>${escapeHtml(item.room)}</td>
      <td>${item.value}</td>
    </tr>
  `).join("");
  const dayRows = data.incidentSeries.map((point) => `
    <tr>
      <td>${escapeHtml(point.label)}</td>
      <td>${point.value}</td>
    </tr>
  `).join("");
  const cameraRows = cameras.length > 0
    ? cameras.map((camera) => `
        <tr>
          <td>${escapeHtml(workspaceNamesById.get(camera.workspace_id) ?? "Workspace")}</td>
          <td>${escapeHtml(camera.name)}</td>
          <td>${escapeHtml(camera.status)}</td>
          <td>${escapeHtml(camera.connection_type)}</td>
          <td>${escapeHtml(camera.last_seen_at ? new Date(camera.last_seen_at).toLocaleString("pt-BR") : "Sem registro")}</td>
        </tr>
      `).join("")
    : `<tr><td colspan="5">Nenhuma câmera cadastrada.</td></tr>`;

  return `
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8" />
        <style>
          body { color: #171C1F; font-family: Arial, sans-serif; margin: 32px; }
          h1 { color: #019BDE; font-size: 28px; margin: 0 0 6px; }
          h2 { border-bottom: 1px solid #D8E6F1; color: #171C1F; font-size: 18px; margin: 28px 0 10px; padding-bottom: 6px; }
          .meta { color: #667085; font-size: 12px; margin-bottom: 18px; }
          .grid { display: grid; gap: 10px; grid-template-columns: repeat(3, 1fr); margin: 18px 0; }
          .metric { background: #F6FAFE; border: 1px solid #E1ECF4; border-radius: 10px; padding: 12px; }
          .metric span { color: #667085; display: block; font-size: 11px; margin-bottom: 6px; }
          .metric strong { font-size: 24px; }
          table { border-collapse: collapse; font-size: 11px; margin-top: 8px; width: 100%; }
          th { background: #EDF6FC; color: #404850; text-align: left; }
          th, td { border: 1px solid #D8E6F1; padding: 7px; vertical-align: top; }
          .note { background: #FFF8E8; border: 1px solid #F4D58D; border-radius: 10px; color: #6B4E00; font-size: 12px; padding: 10px; }
        </style>
      </head>
      <body>
        <h1>Relatório de Insights VARD</h1>
        <div class="meta">
          Gerado em ${escapeHtml(generatedAt)}<br />
          Workspaces: ${escapeHtml(workspaceName)}<br />
          Período: ${escapeHtml(period)}<br />
          Filtro de câmera: ${escapeHtml(cameraName)}
        </div>

        <div class="grid">
          <div class="metric"><span>Total de quedas</span><strong>${data.incidentTotal}</strong></div>
          <div class="metric"><span>Últimas 24h</span><strong>${data.dailyIncidentTotal}</strong></div>
          <div class="metric"><span>Falsas detecções</span><strong>${data.falsePositiveTotal}</strong></div>
        </div>

        <h2>Resumo</h2>
        <p>${escapeHtml(data.dailyIncidentMessage)}</p>

        <h2>Quedas por Cômodo</h2>
        <table>
          <thead><tr><th>Workspace e local</th><th>Total</th></tr></thead>
          <tbody>${roomRows}</tbody>
        </table>

        <h2>Quedas por Dia</h2>
        <table>
          <thead><tr><th>Data</th><th>Total</th></tr></thead>
          <tbody>${dayRows}</tbody>
        </table>

        <h2>Disponibilidade das Câmeras</h2>
        <div class="note">
          ${escapeHtml(data.availabilityMessage)} A disponibilidade histórica ainda depende dos registros de status disponíveis no sistema.
        </div>
        <table>
          <thead><tr><th>Workspace</th><th>Câmera</th><th>Status atual</th><th>Tipo</th><th>Última vez online</th></tr></thead>
          <tbody>${cameraRows}</tbody>
        </table>

        <h2>Histórico de Quedas</h2>
        <table>
          <thead>
            <tr>
              <th>Data</th><th>Workspace</th><th>Câmera</th><th>Local</th>
              <th>Status</th><th>Prob.</th><th>Severidade</th><th>Título</th>
            </tr>
          </thead>
          <tbody>${incidentRows}</tbody>
        </table>
      </body>
    </html>
  `;
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
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
  series: IncidentSeriesPoint[];
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

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.metricCard}>
      <Text numberOfLines={1} style={styles.metricLabel}>{label}</Text>
      <Text numberOfLines={1} style={styles.metricValue}>{value}</Text>
    </View>
  );
}

function IncidentActionButton({
  disabled,
  label,
  onPress,
  selected,
}: {
  disabled: boolean;
  label: string;
  onPress: () => void;
  selected: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.incidentActionButton,
        selected && styles.incidentActionButtonSelected,
        (pressed || disabled) && styles.pressed,
      ]}
    >
      <Text
        style={[
          styles.incidentActionButtonText,
          selected && styles.incidentActionButtonTextSelected,
        ]}
      >
        {label}
      </Text>
    </Pressable>
  );
}

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

function IncidentsChart({ series }: IncidentsChartProps) {
  const width = 294;
  const height = 192;
  const chartTop = 28;
  const chartLeft = 24;
  const plotWidth = 270;
  const plotHeight = 120;
  const min = 0;
  const values = series.length > 0 ? series.map((point) => point.value) : [0, 0];
  const max = Math.max(5, ...values);
  const ticks = [max, max * 0.75, max * 0.5, max * 0.25, min];
  const labels =
    series.length > 0
      ? series.map((point) => point.label)
      : ["--", "--"];

  const points = values.map((value, index) => {
    const divisor = Math.max(1, values.length - 1);
    const x = chartLeft + (index / divisor) * plotWidth;
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
              key={`${label}-${index}`}
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
