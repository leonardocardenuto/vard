import React from "react";
import {
    View,
    Text,
    StyleSheet,
    Image,
    TouchableOpacity,
    ScrollView,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { styles } from "../Workspace";

export default function WorkspaceScreen() {
    return (
        <View style={styles.container}>
            <ScrollView showsVerticalScrollIndicator={false}>


                {/* TITLE */}
                <Text style={styles.title}>Espaço da Família</Text>
                <Text style={styles.subtitle}>Cozinha</Text>

                {/* ALERT CARD */}
                <View style={styles.alertCard}>
                    <View style={styles.alertHeader}>
                        <Ionicons name="warning" size={24} color="#c0392b" />
                        <View style={{ marginLeft: 10 }}>
                            <Text style={styles.alertTitle}>QUEDA DETECTADA</Text>
                            <Text style={styles.alertSubtitle}>
                                Cozinha - 10:32
                            </Text>
                        </View>
                    </View>

                    <TouchableOpacity style={styles.secondaryButton}>
                        <Text style={styles.secondaryText}>Já estou verificando!</Text>
                    </TouchableOpacity>

                    <TouchableOpacity style={styles.primaryButton}>
                        <Text style={styles.primaryText}>
                            Chamar Serviços de Emergência
                        </Text>
                    </TouchableOpacity>
                </View>

                {/* RECENT ACTIVITY */}
                <View style={styles.sectionHeader}>
                    <Text style={styles.sectionTitle}>Atividade Recente</Text>
                    <Text style={styles.live}>Atualização em Tempo Real</Text>
                </View>

                <View style={styles.activityCard}>
                    <Ionicons name="enter-outline" size={24} color="#00a8cc" />
                    <View style={{ marginLeft: 10 }}>
                        <Text style={styles.activityText}>
                            Atividade: Entrou na Sala
                        </Text>
                        <Text style={styles.time}>10:15</Text>
                    </View>
                </View>

                {/* SNAPSHOT */}
                <View style={styles.snapshotCard}>
                    <View style={styles.snapshotHeader}>
                        <Ionicons name="camera-outline" size={24} color="#00a8cc" />
                        <View style={{ marginLeft: 10 }}>
                            <Text style={styles.activityText}>
                                Foto capturada (Quarto)
                            </Text>
                            <Text style={styles.time}>9:45</Text>
                        </View>
                    </View>

                    <View style={styles.imageRow}>
                        <Image
                            source={{ uri: "https://picsum.photos/200/120" }}
                            style={styles.snapshotImage}
                        />
                        <Image
                            source={{ uri: "https://picsum.photos/201/120" }}
                            style={styles.snapshotImage}
                        />
                    </View>
                </View>

                {/* CAREGIVERS */}
                <Text style={styles.sectionTitle}>Família e Cuidadores</Text>

                <View style={styles.caregivers}>
                    <View style={styles.person}>
                        <Image
                            source={{ uri: "https://i.pravatar.cc/101" }}
                            style={styles.personImage}
                        />
                        <Text>Maria</Text>
                    </View>

                    <View style={styles.person}>
                        <Image
                            source={{ uri: "https://i.pravatar.cc/102" }}
                            style={styles.personImage}
                        />
                        <Text>David</Text>
                    </View>

                    <View style={styles.addPerson}>
                        <Text style={{ fontSize: 20 }}>+</Text>
                        <Text>Adicionar</Text>
                    </View>
                </View>
            </ScrollView>

            {/* BOTTOM NAV */}
            <View style={styles.bottomNav}>
                <Ionicons name="home-outline" size={24} color="#999" />
                <View style={styles.activeTab}>
                    <Ionicons name="grid" size={24} color="#fff" />
                </View>
                <Ionicons name="analytics-outline" size={24} color="#999" />
                <Ionicons name="settings-outline" size={24} color="#999" />
            </View>
        </View>
    );
}