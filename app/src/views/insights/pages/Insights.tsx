import { Ionicons } from "@expo/vector-icons";
import { useFonts } from "expo-font";
import { LinearGradient as ExpoLinearGradient } from "expo-linear-gradient";
import { useMemo, useState } from "react";
import { Alert, Pressable, ScrollView, Text, View } from "react-native";
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

type Period = "30 dias" | "90 dias" | "180 dias";
type InsightMode = "Geral" | "Saúde" | "Atividade";

const PERIODS: Period[] = ["30 dias", "90 dias", "180 dias"];
const MODES: InsightMode[] = ["Geral", "Saúde", "Atividade"];

const CHART_BY_PERIOD: Record<Period, number[]> = {
  "30 dias": [2.9, 3.1, 3.6, 3.8, 4.1, 3.7, 3.2, 3.5],
  "90 dias": [3.3, 3.3, 3.7, 4.0, 4.3, 4.2, 3.8, 3.9, 4.3, 4.4, 4.0],
  "180 dias": [3.1, 3.5, 3.4, 3.8, 4.1, 3.6, 3.9, 4.2, 4.0, 4.1, 3.7],
};

const ROOM_INCIDENTS = [
  { room: "Quarto", value: 5, barStyle: styles.roomBarQuarto },
  { room: "Sala", value: 3, barStyle: styles.roomBarSala },
  { room: "Cozinha", value: 2, barStyle: styles.roomBarCozinha },
  { room: "Banheiro", value: 1, barStyle: styles.roomBarBanheiro },
];

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
  const [period, setPeriod] = useState<Period>("90 dias");
  const [mode, setMode] = useState<InsightMode>("Geral");
  const [isPeriodMenuOpen, setIsPeriodMenuOpen] = useState(false);
  const [exportLabel, setExportLabel] = useState("Export Monthly Report\n(PDF)");

  const chartValues = useMemo(() => CHART_BY_PERIOD[period], [period]);

  if (!fontsLoaded) {
    return null;
  }

  function cycleMode() {
    const currentIndex = MODES.indexOf(mode);
    const nextMode = MODES[(currentIndex + 1) % MODES.length];
    setMode(nextMode);
  }

  function selectPeriod(nextPeriod: Period) {
    setPeriod(nextPeriod);
    setIsPeriodMenuOpen(false);
  }

  function handleExportReport() {
    setExportLabel("Relatório pronto\n(PDF)");
    Alert.alert("Relatório gerado", `Relatório de ${period} preparado para exportação.`);
  }

  return (
    <LayoutWithNavbar>
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
                  height={40}
                  style={styles.title}
                  text="Insights"
                  width={160}
                  y={31}
                />
                <Text style={styles.mode}>{mode}</Text>
              </View>
              <Ionicons color={INSIGHTS_COLORS.gradientMiddle} name="chevron-forward" size={36} />
            </Pressable>
            <Text style={styles.subtitle}>Resumo de atividades e saúde.</Text>
          </View>

          <View style={styles.cardLarge}>
            <View style={styles.incidentsHeader}>
              <View>
                <Text style={styles.cardTitle}>Incidentes</Text>
                <Text style={styles.cardSubtitle}>Incidentes x Dias</Text>
              </View>

              <View style={styles.periodArea}>
                <Pressable
                  accessibilityLabel="Selecionar período dos incidentes"
                  accessibilityRole="button"
                  onPress={() => setIsPeriodMenuOpen((current) => !current)}
                  style={({ pressed }) => [
                    styles.periodButton,
                    pressed && styles.pressed,
                  ]}
                >
                  <Text style={styles.periodText}>Últimos{"\n"}{period}</Text>
                  <Ionicons color={INSIGHTS_COLORS.gradientMiddle} name="chevron-forward" size={28} />
                </Pressable>

                {isPeriodMenuOpen ? (
                  <View style={styles.periodMenu}>
                    {PERIODS.map((item) => (
                      <Pressable
                        accessibilityRole="button"
                        key={item}
                        onPress={() => selectPeriod(item)}
                        style={({ pressed }) => [
                          styles.periodMenuItem,
                          item === period && styles.periodMenuItemActive,
                          pressed && styles.pressed,
                        ]}
                      >
                        <Text
                          style={[
                            styles.periodMenuText,
                            item === period && styles.periodMenuTextActive,
                          ]}
                        >
                          {item}
                        </Text>
                      </Pressable>
                    ))}
                  </View>
                ) : null}
              </View>
            </View>

            <IncidentsChart values={chartValues} />
          </View>

          <View style={styles.cardRooms}>
            <Text style={styles.roomsTitle}>Incidentes por Cômodo</Text>
            <View style={styles.roomList}>
              {ROOM_INCIDENTS.map((item) => (
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
              <Ionicons color={INSIGHTS_COLORS.gradientMiddle} name="ribbon-outline" size={40} />
            </View>
            <Text style={styles.dailyLabel}>TOTAL DAILY INCIDENTS</Text>
            <Text style={styles.dailyValue}>0</Text>
            <Text style={styles.dailyText}>
              Nenhuma anomalia detectada nas{"\n"}últimas 24 horas.
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
            <Text style={styles.cameraTitle}>Câmera 1</Text>
            <Text style={styles.cameraSubtitle}>Últimas 24 horas</Text>
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
            accessibilityLabel="Exportar relatório mensal em PDF"
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
    </LayoutWithNavbar>
  );
}

type IncidentsChartProps = {
  values: number[];
};

type GradientTitleProps = {
  fontSize: number;
  height: number;
  style: object;
  text: string;
  width: number;
  y: number;
};

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
            <Stop offset="8%" stopColor={INSIGHTS_COLORS.gradientStart} stopOpacity="0.28" />
            <Stop offset="38%" stopColor={INSIGHTS_COLORS.gradientMiddle} stopOpacity="0.16" />
            <Stop offset="100%" stopColor={INSIGHTS_COLORS.gradientEnd} stopOpacity="0" />
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
        <Path d={path} fill="none" stroke="url(#chartLineGradient)" strokeLinecap="round" strokeWidth={2.5} />

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
