import { RouteProp, useRoute } from "@react-navigation/native";
import { LinearGradient as ExpoLinearGradient } from "expo-linear-gradient";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import Svg, {
  Defs,
  LinearGradient,
  Stop,
  Text as SvgText,
} from "react-native-svg";
import { LayoutWithNavbar } from "../../../components/LayoutWithNavbar";
import { AppTabParamList } from "../../../navigation/types";

import NoIncidentsIcon from "../../../../assets/no_incident_icon.svg";
import AmbulanceIcon from "../../../../assets/ambulance_icon.svg";
import PoliceIcon from "../../../../assets/police_icon.svg";
import FirefighterIcon from "../../../../assets/firefighters_icon.svg";

type HomeRoute = RouteProp<AppTabParamList, "Home">;

const REAL_TIME_TITLE_GRADIENT_ID = "realTimeMonitoringTitleGradient";
const STATUS_CARD_GRADIENT_COLORS = ["#03CDF4", "#019BDE", "#01EBD0"] as const;
const STATUS_CARD_GRADIENT_LOCATIONS = [0.08, 0.38, 1] as const;

const ALERTS = [
  { id: 1, text: "Alerta de exemplo 1" },
  { id: 2, text: "Alerta de exemplo 2" },
  { id: 3, text: "Alerta de exemplo 3" },
];

export function Home() {
  const route = useRoute<HomeRoute>();
  const userName = route.params?.userName?.trim() || "usuario";
  const alerts = ALERTS;
  const hasAlerts = alerts.length > 0;

  return (
    <LayoutWithNavbar>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <View>
          <Text style={styles.sectionTitle}>Alertas</Text>
          <View style={styles.alertsContainer}>
            {hasAlerts ? (
              alerts.map((alert) => (
                <Pressable
                  accessibilityLabel={`Abrir ${alert.text}`}
                  accessibilityRole="button"
                  key={alert.id}
                  onPress={() => console.log(`Alerta ${alert.id} pressionado`)}
                  style={({ pressed }) => [
                    styles.alertButton,
                    pressed && styles.alertButtonPressed,
                  ]}
                >
                  <Text style={styles.alertText}>{alert.text}</Text>
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
                    fill={`url(#${REAL_TIME_TITLE_GRADIENT_ID})`}
                    fontSize={16}
                    fontWeight="900"
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
              O AMBIENTE DOMESTICO ESTA SEGURO
            </Text>
            <Text style={styles.emergencyButtonsDescriptionText}>
              Monitoramento ativo para quedas, incendios e brigas/agitacao.
              Todos os sensores estao transmitindo dados em tempo real.
            </Text>
            <Pressable
              onPress={() => console.log(`SAMU acionado`)}
              style={styles.emergencyButton}
            >
              <AmbulanceIcon />
              <Text style={styles.emergencyButtonText}>SAMU (192)</Text>
            </Pressable>
            <Pressable
              onPress={() => console.log(`Policia acionada`)}
              style={styles.emergencyButton}
            >
              <PoliceIcon />
              <Text style={styles.emergencyButtonText}>Policia (190)</Text>
            </Pressable>
            <Pressable
              onPress={() => console.log(`Bombeiros acionados`)}
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
  alertButton: {
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 12,
    width: "100%",
  },
  alertButtonPressed: {
    backgroundColor: "rgba(1, 155, 222, 0.08)",
  },
  alertText: {
    color: "#404850",
    fontSize: 16,
    lineHeight: 24,
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
