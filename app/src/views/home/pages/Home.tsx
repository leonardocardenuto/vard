import { RouteProp, useFocusEffect, useRoute } from "@react-navigation/native";
import { LinearGradient as ExpoLinearGradient } from "expo-linear-gradient";
import { useCallback, useState, useEffect, } from "react";
import {
  ActivityIndicator,
  Linking,
  Pressable,
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
import {
  HOME_FONTS,
  styles,
} from "../styles/Home";

import AmbulanceIcon from "../../../../assets/ambulance_icon.svg";
import FirefighterIcon from "../../../../assets/firefighters_icon.svg";
import NoIncidentsIcon from "../../../../assets/no_incident_icon.svg";
import PoliceIcon from "../../../../assets/police_icon.svg";

type HomeRoute = RouteProp<AppTabParamList, "Home">;

const REAL_TIME_TITLE_GRADIENT_ID = "realTimeMonitoringTitleGradient";
const STATUS_CARD_GRADIENT_COLORS = ["#03CDF4", "#019BDE", "#01EBD0"] as const;
const STATUS_CARD_GRADIENT_LOCATIONS = [0.08, 0.38, 1] as const;

const openDialer = (phoneNumber: string) => {
  Linking.openURL(`tel:${phoneNumber}`);
};

export function Home() {
  const route = useRoute<HomeRoute>();
  const accessToken = route.params?.accessToken ?? "";
  const [alerts, setAlerts] = useState<NotificationResponse[]>([]);
  const [isLoadingAlerts, setIsLoadingAlerts] = useState(true);
  const [alertsError, setAlertsError] = useState("");
  const hasAlerts = alerts.length > 0;

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
        workspaces.map((workspace) =>
          listNotifications(accessToken, workspace.id),
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

  return (
    <LayoutWithNavbar>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <View>
          <Text style={styles.sectionTitle}>Últimos alertas</Text>
          <View style={styles.alertsContainer}>
            {hasAlerts ? (
              alerts.map((alert) => (
                <Pressable
                  accessibilityLabel={`Abrir ${alert.title}`}
                  accessibilityRole="button"
                  key={alert.id}
                  onPress={() => console.log(`Alerta ${alert.id} pressionado`)}
                  style={({ pressed }) => [
                    styles.alertButton,
                    pressed && styles.alertButtonPressed,
                  ]}
                >
                  <View style={styles.alertHeader}>
                    <Text style={styles.alertTitle}>{alert.title}</Text>
                    <Text
                      style={[
                        styles.alertSeverity,
                        { color: getSeverityColor(alert.severity) },
                      ]}
                    >
                      {formatSeverity(alert.severity)}
                    </Text>
                  </View>
                  <Text style={styles.alertSubtitle}>{alert.body}</Text>
                  <Text style={styles.alertDate}>
                    {formatAlertDate(alert.created_at)}
                  </Text>
                </Pressable>
              ))
            ) : (
              <View
                accessibilityLabel="Nenhum incidente detectado hoje"
                accessibilityRole="summary"
                style={styles.noAlerts}
              >
                <NoIncidentsIcon
                  height={30}
                  style={styles.noAlertsIcon}
                  width={30}
                />
                <Text style={styles.noAlertsText}>
                  Nenhum incidente detectado hoje.
                </Text>
              </View>
            )}
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Monitoramento em tempo real</Text>
          <ExpoLinearGradient
            colors={["#03CDF4", "#019BDE", "#01EBD0"]}
            locations={[0.08, 0.38, 1]}
            start={{ x: 0, y: 0 }}
            end={{ x: 0, y: 1 }}
            style={styles.realTimeMonitoringBorder}
          >
            <View style={styles.realTimeMonitoringContainer}>
              <View style={styles.realTimeMonitoringHeader}>
                <NoIncidentsIcon height={22} width={22} />
                <View style={styles.realTimeMonitoringTitle}>
                  <Svg height={24} width={132}>
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
                      fontFamily={HOME_FONTS.semiBold}
                      fontSize={24}
                      x={0}
                      y={18}
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

function formatSeverity(severity: NotificationResponse["severity"]) {
  const labels: Record<NotificationResponse["severity"], string> = {
    critical: "Critico",
    high: "Alto",
    medium: "Medio",
    low: "Baixo",
  };

  return labels[severity] ?? severity;
}
function getSeverityColor(severity: NotificationResponse["severity"]) {
  const colors: Record<NotificationResponse["severity"], string> = {
    critical: "#D32F2F",
    high: "#F57C00",
    medium: "#FBC02D",
    low: "#388E3C",
  };

  return colors[severity] ?? "#019BDE";
}

function formatAlertDate(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return date.toLocaleString("pt-BR", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit",
  });
}
