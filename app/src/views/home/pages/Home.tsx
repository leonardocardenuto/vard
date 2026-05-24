import { RouteProp, useFocusEffect, useRoute } from "@react-navigation/native";
import { LinearGradient as ExpoLinearGradient } from "expo-linear-gradient";
import { useCallback, useState } from "react";
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

import NoIncidentsIcon from "../../../../assets/no_incident_icon.svg";
import AmbulanceIcon from "../../../../assets/ambulance_icon.svg";
import PoliceIcon from "../../../../assets/police_icon.svg";
import FirefighterIcon from "../../../../assets/firefighters_icon.svg";

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
          <Text style={styles.sectionTitle}>Alertas</Text>
          <View style={hasAlerts ? styles.alertCard : styles.alertsContainer}>
            {isLoadingAlerts ? (
              <View style={styles.loadingAlerts}>
                <ActivityIndicator color="#019BDE" />
                <Text style={styles.loadingAlertsText}>
                  Carregando alertas...
                </Text>
              </View>
            ) : alertsError ? (
              <Text style={styles.alertsErrorText}>{alertsError}</Text>
            ) : hasAlerts ? (
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
          <View style={styles.realTimeMonitoringContainer}>
            <View style={styles.realTimeMonitoringHeader}>
              <NoIncidentsIcon height={24} width={24} />
              <View style={styles.realTimeMonitoringTitle}>
                <Svg height={24} width={112}>
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
                    fontFamily="System"
                    fontWeight="700"
                    fontSize={16}
                    fill={`url(#${REAL_TIME_TITLE_GRADIENT_ID})`}
                    x={0}
                    y={18}
                  >
                    TUDO BEM!
                  </SvgText>
                </Svg>
              </View>
            </View>
            <Text style={styles.realTimeMonitoringText}>
              O monitoramento está ativo.
            </Text>
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

const styles = StyleSheet.create({
  content: {
    padding: 30,
    paddingBottom: 144,
  },
  section: {
    marginTop: 24,
  },
  sectionTitle: {
    color: "#101828",
    fontSize: 24,
    lineHeight: 30,
    fontWeight: "700",
    textAlign: "left",
  },
  alertsContainer: {
    marginTop: 16,
    backgroundColor: "#EAEEF2",
    alignItems: "flex-start",
    padding: 8,
    borderRadius: 12,
    borderColor: "#BFC7D1",
    borderWidth: 1,
  },
  noAlerts: {
    padding: 24,
    width: "100%",
    alignItems: "center",
  },
  noAlertsIcon: {
    alignSelf: "center",
    marginBottom: 8,
  },
  noAlertsText: {
    color: "#404850",
    fontSize: 16,
    lineHeight: 22,
    textAlign: "center",
  },
  loadingAlerts: {
    alignItems: "center",
    padding: 24,
    width: "100%",
  },
  loadingAlertsText: {
    color: "#404850",
    fontSize: 14,
    lineHeight: 20,
    marginTop: 8,
    textAlign: "center",
  },
  alertsErrorText: {
    color: "#A33131",
    fontSize: 14,
    lineHeight: 20,
    padding: 16,
  },
  alertButton: {
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 12,
    width: "100%",
  },
  alertButtonPressed: {
    backgroundColor: "rgba(1, 155, 222, 0.08)",
  },
  alertCard: {
    backgroundColor: "#FDECEA",
    borderColor: "#E74C3C",
    borderRadius: 15,
    borderWidth: 1,
    marginBottom: 20,
    padding: 15,
  },
  alertHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    width: "100%",
    marginBottom: 10,
  },

  alertTitle: {
    color: "#019BDE",
    fontWeight: "bold",
    flex: 1,
  },
  alertSubtitle: {
    color: "#555555",
  },

  alertSeverity: {
    color: "#019BDE",
    fontSize: 12,
    fontWeight: "700",
    lineHeight: 16,
    textTransform: "uppercase",
  },
  alertDate: {
    color: "#667085",
    fontSize: 12,
    lineHeight: 16,
    marginTop: 6,
  },
  realTimeMonitoringContainer: {
    marginTop: 16,
    backgroundColor: "#EAEEF2",
    borderRadius: 12,
    borderColor: "#BFC7D1",
    borderWidth: 1,
    overflow: "hidden",
  },
  realTimeMonitoringHeader: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingTop: 16,
  },
  realTimeMonitoringTitle: {
    marginLeft: 8,
  },
  realTimeMonitoringText: {
    color: "#171C1F",
    fontSize: 22,
    fontWeight: "500",
    lineHeight: 24,
    paddingHorizontal: 16,
    paddingBottom: 32,
    paddingTop: 8,
  },
  emergencyButtonsContainer: {
    minHeight: 180,
    borderRadius: 12,
    padding: 24,
    flexDirection: "column",
    justifyContent: "center",
    alignItems: "center",
    overflow: "hidden",
  },
  emergencyButtonsEstateText: {
    color: "#FFFFFF",
    fontSize: 22,
    fontWeight: "900",
    lineHeight: 28,
    textAlign: "center",
  },
  emergencyButtonsDescriptionText: {
    marginTop: 12,
    color: "#FFFFFF",
    fontSize: 15,
    fontWeight: "600",
    lineHeight: 22,
    textAlign: "center",
  },
  emergencyButton: {
    marginTop: 16,
    flexDirection: "row",
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 8,
    width: "100%",
  },
  emergencyButtonText: {
    padding: 12,
    fontSize: 18,
    color: "#03CDF4",
    fontWeight: "600",
  },
});
