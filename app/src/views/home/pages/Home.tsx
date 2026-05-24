import { RouteProp, useRoute } from "@react-navigation/native";
import { LinearGradient as ExpoLinearGradient } from "expo-linear-gradient";
import { Pressable, ScrollView, Text, View } from "react-native";
import Svg, {
  Defs,
  LinearGradient,
  Stop,
  Text as SvgText,
} from "react-native-svg";
import { LayoutWithNavbar } from "../../../components/LayoutWithNavbar";
import { AppTabParamList } from "../../../navigation/types";
import {
  HOME_FONTS,
  REAL_TIME_TITLE_GRADIENT_ID,
  STATUS_CARD_GRADIENT_COLORS,
  STATUS_CARD_GRADIENT_LOCATIONS,
  styles,
} from "../styles/Home";

import AmbulanceIcon from "../../../../assets/ambulance_icon.svg";
import FirefighterIcon from "../../../../assets/firefighters_icon.svg";
import NoIncidentsIcon from "../../../../assets/no_incident_icon.svg";
import PoliceIcon from "../../../../assets/police_icon.svg";

type HomeRoute = RouteProp<AppTabParamList, "Home">;

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
              <Text style={styles.emergencyButtonText}>Polícia (190)</Text>
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
