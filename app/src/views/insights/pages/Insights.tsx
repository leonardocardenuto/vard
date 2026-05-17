import { Ionicons } from "@expo/vector-icons";
import { useFonts } from "expo-font";
import { LinearGradient as ExpoLinearGradient } from "expo-linear-gradient";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Animated,
  Modal,
  PanResponder,
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
  INSIGHTS_COLORS,
  INSIGHTS_FONTS,
  INSIGHTS_GRADIENT_COLORS,
  INSIGHTS_GRADIENT_LOCATIONS,
  styles,
} from "../Insights";

type Period = "Ultimos 15 dias" | "Ultimos 30 dias" | "Ultimos 60 dias" | "Ultimos 90 dias";
type InsightMode = "Geral" | "Saude" | "Atividade";
type CameraFilter = "Cozinha" | "Quarto" | "Sala de Estar";

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

const CAMERA_OPTIONS: CameraFilter[] = ["Cozinha", "Quarto", "Sala de Estar"];
const MODES: InsightMode[] = ["Geral", "Saude", "Atividade"];
const DEFAULT_PERIOD: Period = "Ultimos 90 dias";
const DEFAULT_CAMERA: CameraFilter = "Quarto";

const ROOM_BAR_STYLES = {
  quarto: styles.roomBarQuarto,
  sala: styles.roomBarSala,
  cozinha: styles.roomBarCozinha,
  banheiro: styles.roomBarBanheiro,
} as const;

const CAMERA_DATA_BY_PERIOD: Record<Period, Record<CameraFilter, CameraData>> = {
  "Ultimos 15 dias": {
    Cozinha: {
      activityLabel: "Camera Cozinha",
      chartValues: [2.1, 2.4, 2.6, 2.8, 2.4, 2.2, 2.5, 2.7],
      incidentTotal: 6,
      roomIncidents: [
        { room: "Cozinha", value: 4, barStyle: ROOM_BAR_STYLES.cozinha },
        { room: "Quarto", value: 3, barStyle: ROOM_BAR_STYLES.quarto },
        { room: "Sala", value: 2, barStyle: ROOM_BAR_STYLES.sala },
        { room: "Banheiro", value: 1, barStyle: ROOM_BAR_STYLES.banheiro },
      ],
    },
    Quarto: {
      activityLabel: "Camera Quarto",
      chartValues: [2.9, 3.0, 3.2, 3.5, 3.1, 2.9, 3.3, 3.4],
      incidentTotal: 8,
      roomIncidents: [
        { room: "Quarto", value: 5, barStyle: ROOM_BAR_STYLES.quarto },
        { room: "Sala", value: 2, barStyle: ROOM_BAR_STYLES.sala },
        { room: "Cozinha", value: 2, barStyle: ROOM_BAR_STYLES.cozinha },
        { room: "Banheiro", value: 1, barStyle: ROOM_BAR_STYLES.banheiro },
      ],
    },
    "Sala de Estar": {
      activityLabel: "Camera Sala",
      chartValues: [1.8, 2.0, 2.2, 2.6, 2.5, 2.3, 2.8, 2.9],
      incidentTotal: 5,
      roomIncidents: [
        { room: "Sala", value: 4, barStyle: ROOM_BAR_STYLES.sala },
        { room: "Quarto", value: 2, barStyle: ROOM_BAR_STYLES.quarto },
        { room: "Cozinha", value: 1, barStyle: ROOM_BAR_STYLES.cozinha },
        { room: "Banheiro", value: 1, barStyle: ROOM_BAR_STYLES.banheiro },
      ],
    },
  },
  "Ultimos 30 dias": {
    Cozinha: {
      activityLabel: "Camera Cozinha",
      chartValues: [2.9, 3.1, 3.6, 3.8, 4.1, 3.7, 3.2, 3.5],
      incidentTotal: 11,
      roomIncidents: [
        { room: "Cozinha", value: 5, barStyle: ROOM_BAR_STYLES.cozinha },
        { room: "Quarto", value: 4, barStyle: ROOM_BAR_STYLES.quarto },
        { room: "Sala", value: 3, barStyle: ROOM_BAR_STYLES.sala },
        { room: "Banheiro", value: 1, barStyle: ROOM_BAR_STYLES.banheiro },
      ],
    },
    Quarto: {
      activityLabel: "Camera Quarto",
      chartValues: [3.3, 3.4, 3.7, 4.0, 4.3, 4.1, 3.9, 4.2],
      incidentTotal: 9,
      roomIncidents: [
        { room: "Quarto", value: 5, barStyle: ROOM_BAR_STYLES.quarto },
        { room: "Sala", value: 3, barStyle: ROOM_BAR_STYLES.sala },
        { room: "Cozinha", value: 2, barStyle: ROOM_BAR_STYLES.cozinha },
        { room: "Banheiro", value: 1, barStyle: ROOM_BAR_STYLES.banheiro },
      ],
    },
    "Sala de Estar": {
      activityLabel: "Camera Sala",
      chartValues: [2.4, 2.7, 3.1, 3.2, 3.5, 3.4, 3.0, 3.3],
      incidentTotal: 7,
      roomIncidents: [
        { room: "Sala", value: 5, barStyle: ROOM_BAR_STYLES.sala },
        { room: "Quarto", value: 3, barStyle: ROOM_BAR_STYLES.quarto },
        { room: "Cozinha", value: 2, barStyle: ROOM_BAR_STYLES.cozinha },
        { room: "Banheiro", value: 1, barStyle: ROOM_BAR_STYLES.banheiro },
      ],
    },
  },
  "Ultimos 60 dias": {
    Cozinha: {
      activityLabel: "Camera Cozinha",
      chartValues: [3.0, 3.2, 3.8, 4.0, 4.2, 4.1, 3.7, 3.9],
      incidentTotal: 14,
      roomIncidents: [
        { room: "Cozinha", value: 5, barStyle: ROOM_BAR_STYLES.cozinha },
        { room: "Quarto", value: 4, barStyle: ROOM_BAR_STYLES.quarto },
        { room: "Sala", value: 4, barStyle: ROOM_BAR_STYLES.sala },
        { room: "Banheiro", value: 2, barStyle: ROOM_BAR_STYLES.banheiro },
      ],
    },
    Quarto: {
      activityLabel: "Camera Quarto",
      chartValues: [3.1, 3.4, 3.9, 4.3, 4.5, 4.2, 4.0, 4.3],
      incidentTotal: 12,
      roomIncidents: [
        { room: "Quarto", value: 5, barStyle: ROOM_BAR_STYLES.quarto },
        { room: "Sala", value: 4, barStyle: ROOM_BAR_STYLES.sala },
        { room: "Cozinha", value: 3, barStyle: ROOM_BAR_STYLES.cozinha },
        { room: "Banheiro", value: 1, barStyle: ROOM_BAR_STYLES.banheiro },
      ],
    },
    "Sala de Estar": {
      activityLabel: "Camera Sala",
      chartValues: [2.8, 3.0, 3.2, 3.6, 3.8, 3.7, 3.4, 3.6],
      incidentTotal: 10,
      roomIncidents: [
        { room: "Sala", value: 5, barStyle: ROOM_BAR_STYLES.sala },
        { room: "Quarto", value: 4, barStyle: ROOM_BAR_STYLES.quarto },
        { room: "Cozinha", value: 2, barStyle: ROOM_BAR_STYLES.cozinha },
        { room: "Banheiro", value: 2, barStyle: ROOM_BAR_STYLES.banheiro },
      ],
    },
  },
  "Ultimos 90 dias": {
    Cozinha: {
      activityLabel: "Camera Cozinha",
      chartValues: [3.3, 3.3, 3.7, 4.0, 4.3, 4.2, 3.8, 3.9, 4.3, 4.4, 4.0],
      incidentTotal: 16,
      roomIncidents: [
        { room: "Cozinha", value: 5, barStyle: ROOM_BAR_STYLES.cozinha },
        { room: "Quarto", value: 4, barStyle: ROOM_BAR_STYLES.quarto },
        { room: "Sala", value: 3, barStyle: ROOM_BAR_STYLES.sala },
        { room: "Banheiro", value: 1, barStyle: ROOM_BAR_STYLES.banheiro },
      ],
    },
    Quarto: {
      activityLabel: "Camera Quarto",
      chartValues: [3.2, 3.5, 3.9, 4.3, 4.5, 4.2, 3.9, 4.0, 4.4, 4.5, 4.1],
      incidentTotal: 12,
      roomIncidents: [
        { room: "Quarto", value: 5, barStyle: ROOM_BAR_STYLES.quarto },
        { room: "Sala", value: 3, barStyle: ROOM_BAR_STYLES.sala },
        { room: "Cozinha", value: 2, barStyle: ROOM_BAR_STYLES.cozinha },
        { room: "Banheiro", value: 1, barStyle: ROOM_BAR_STYLES.banheiro },
      ],
    },
    "Sala de Estar": {
      activityLabel: "Camera Sala",
      chartValues: [2.9, 3.1, 3.4, 3.7, 3.9, 3.8, 3.5, 3.6, 3.9, 4.1, 3.8],
      incidentTotal: 10,
      roomIncidents: [
        { room: "Sala", value: 5, barStyle: ROOM_BAR_STYLES.sala },
        { room: "Quarto", value: 3, barStyle: ROOM_BAR_STYLES.quarto },
        { room: "Cozinha", value: 2, barStyle: ROOM_BAR_STYLES.cozinha },
        { room: "Banheiro", value: 1, barStyle: ROOM_BAR_STYLES.banheiro },
      ],
    },
  },
};

const ACTIVITY_SEGMENTS = [
  styles.activitySegmentFirst,
  styles.activitySegmentSecond,
  styles.activitySegmentThird,
];

export function Insights() {
  const [fontsLoaded] = useFonts({
    [INSIGHTS_FONTS.manrope]: require("../../../../assets/fonts/Manrope.ttf"),
    [INSIGHTS_FONTS.regular]: require("../../../../assets/fonts/Poppins-Regular.ttf"),
    [INSIGHTS_FONTS.medium]: require("../../../../assets/fonts/Poppins-Medium.ttf"),
    [INSIGHTS_FONTS.bold]: require("../../../../assets/fonts/Poppins-Bold.ttf"),
    [INSIGHTS_FONTS.extraBold]: require("../../../../assets/fonts/Poppins-ExtraBold.ttf"),
    [INSIGHTS_FONTS.black]: require("../../../../assets/fonts/Poppins-Black.ttf"),
  });
  const [period, setPeriod] = useState<Period | null>(DEFAULT_PERIOD);
  const [mode, setMode] = useState<InsightMode>("Geral");
  const [selectedCamera, setSelectedCamera] = useState<CameraFilter | null>(DEFAULT_CAMERA);
  const [isFilterSheetOpen, setIsFilterSheetOpen] = useState(false);
  const [exportLabel, setExportLabel] = useState("Export Monthly Report");
  const sheetAnimation = useRef(new Animated.Value(0)).current;
  const sheetDragY = useRef(new Animated.Value(0)).current;

  const effectivePeriod = period ?? DEFAULT_PERIOD;
  const effectiveCamera = selectedCamera ?? DEFAULT_CAMERA;
  const selectedData = useMemo(
    () => CAMERA_DATA_BY_PERIOD[effectivePeriod][effectiveCamera],
    [effectiveCamera, effectivePeriod],
  );

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

  function cycleMode() {
    const currentIndex = MODES.indexOf(mode);
    const nextMode = MODES[(currentIndex + 1) % MODES.length];
    setMode(nextMode);
  }

  function handleExportReport() {
    setExportLabel("Relatorio pronto");
    Alert.alert(
      "Relatorio gerado",
      `Relatorio de ${effectivePeriod.toLowerCase()} para ${effectiveCamera.toLowerCase()} preparado para exportacao.`,
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

  return (
    <LayoutWithNavbar>
      <View style={styles.page}>
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.screen}>
            <View style={styles.hero}>
              <Pressable
                accessibilityLabel="Alternar categoria de insights"
                accessibilityRole="button"
                onPress={cycleMode}
                style={({ pressed }) => [styles.modeButton, pressed && styles.pressed]}
              >
                <View style={styles.titleLine}>
                  <GradientTitle
                    fontSize={40}
                    height={42}
                    style={styles.title}
                    text="Insights"
                    width={160}
                    y={31}
                  />
                  <Text style={styles.mode}>{mode}</Text>
                </View>
                <Ionicons
                  color={INSIGHTS_COLORS.gradientMiddle}
                  name="chevron-forward"
                  size={36}
                />
              </Pressable>
              <Text style={styles.subtitle}>Resumo de atividades e saude.</Text>
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
                    style={({ pressed }) => [styles.filterButton, pressed && styles.pressed]}
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
              <Text style={styles.dailyValue}>{selectedData.incidentTotal}</Text>
              <Text style={styles.dailyText}>
                Nenhuma anomalia detectada nas ultimas 24 horas.
              </Text>
            </View>

            <GradientTitle
              fontSize={40}
              height={52}
              style={styles.activityTitle}
              text="Atividade"
              width={190}
              y={39}
            />

            <View style={styles.activityCard}>
              <Text style={styles.cameraTitle}>{selectedData.activityLabel}</Text>
              <Text style={styles.cameraSubtitle}>Ultimas 24 horas</Text>
              <View style={styles.activityChart}>
                <View style={styles.activityTrack}>
                  {ACTIVITY_SEGMENTS.map((segmentStyle, index) => (
                    <View key={index} style={[styles.activitySegment, segmentStyle]} />
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
              style={({ pressed }) => [styles.exportButton, pressed && styles.pressed]}
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

        <Modal animationType="none" onRequestClose={closeFilterSheet} transparent visible={isFilterSheetOpen}>
          <View style={styles.bottomSheetRoot}>
            <Pressable
              accessibilityLabel="Fechar filtros"
              accessibilityRole="button"
              onPress={closeFilterSheet}
              style={styles.bottomSheetBackdropPressable}
            >
              <Animated.View
                pointerEvents="none"
                style={[styles.bottomSheetBackdrop, { opacity: backdropOpacity }]}
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
                {CAMERA_OPTIONS.map((item) => (
                  <FilterOptionButton
                    iconName="videocam-outline"
                    key={item}
                    label={item}
                    onPress={() => toggleCameraFilter(item)}
                    selected={item === selectedCamera}
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
                <Text style={styles.filterApplyButtonText}>Aplicar filtros</Text>
              </Pressable>
            </Animated.View>
          </View>
        </Modal>
      </View>
    </LayoutWithNavbar>
  );
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

function GradientTitle({ fontSize, height, style, text, width, y }: GradientTitleProps) {
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
        fontFamily={INSIGHTS_FONTS.manrope}
        fontSize={fontSize}
        fontWeight="900"
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
  const min = 1;
  const max = 5;
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

        {[5, 4, 3, 2, 1].map((tick) => {
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
                {String(tick).padStart(2, "0")}
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
