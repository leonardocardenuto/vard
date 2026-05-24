import { Feather, Ionicons } from '@expo/vector-icons';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Image, Pressable, ScrollView, Text, TouchableOpacity, View } from 'react-native';

import { LayoutWithNavbar } from '../../../components/LayoutWithNavbar';
import { ApiRequestError, CameraResponse, listCameras } from '../../../lib/api';
import { WorkspaceStackParamList } from '../types/workspace';
import { styles } from '../styles/workspace_details';

type Props = NativeStackScreenProps<WorkspaceStackParamList, 'WorkspaceDetails'>;

export default function WorkspaceDetailsScreen({ navigation, route }: Props) {
  const { accessToken, workspace } = route.params;
  const [cameras, setCameras] = useState<CameraResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    async function loadWorkspaceDetails() {
      try {
        setErrorMessage('');
        setIsLoading(true);
        setCameras(await listCameras(accessToken, workspace.id));
      } catch (error) {
        setErrorMessage(
          error instanceof ApiRequestError ? error.message : 'Nao foi possivel carregar os detalhes.'
        );
      } finally {
        setIsLoading(false);
      }
    }

    void loadWorkspaceDetails();
  }, [accessToken, workspace.id]);

  const mainCamera = cameras[0];
  const secondCamera = cameras[1];
  const roomName = mainCamera?.name ?? 'Cozinha';
  const snapshotCamera = secondCamera?.name ?? mainCamera?.name ?? 'Quarto';
  const alertTime = useMemo(
    () => new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }),
    []
  );

  return (
    <LayoutWithNavbar>
      <View style={styles.container}>
        <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
          <View style={styles.headerRow}>
            <Pressable onPress={() => navigation.goBack()} style={styles.backButton}>
              <Feather color="#111827" name="chevron-left" size={20} />
            </Pressable>
            <View>
              <Text numberOfLines={1} style={styles.title}>{workspace.name}</Text>
              <Text numberOfLines={1} style={styles.subtitle}>{roomName}</Text>
            </View>
          </View>

          {errorMessage ? <Text style={styles.errorText}>{errorMessage}</Text> : null}

          <View style={styles.alertCard}>
            <View style={styles.alertHeader}>
              <Ionicons color="#C0392B" name="warning" size={24} />
              <View style={{ marginLeft: 10 }}>
                <Text style={styles.alertTitle}>QUEDA DETECTADA</Text>
                <Text style={styles.alertSubtitle}>{roomName} - {alertTime}</Text>
              </View>
            </View>

            <TouchableOpacity style={styles.secondaryButton}>
              <Text style={styles.secondaryText}>Ja estou verificando!</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.primaryButton}>
              <Text style={styles.primaryText}>Chamar Servicos de Emergencia</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Atividade Recente</Text>
            <Text style={styles.live}>Atualizacao em Tempo Real</Text>
          </View>

          <View style={styles.activityCard}>
            <Ionicons color="#00A8CC" name="enter-outline" size={24} />
            <View style={{ marginLeft: 10 }}>
              <Text style={styles.activityText}>
                {isLoading ? 'Carregando atividade...' : `Atividade: ${mainCamera ? 'Camera ativa' : 'Nenhuma camera cadastrada'}`}
              </Text>
              <Text style={styles.time}>{alertTime}</Text>
            </View>
          </View>

          <View style={styles.snapshotCard}>
            <View style={styles.snapshotHeader}>
              <Ionicons color="#00A8CC" name="camera-outline" size={24} />
              <View style={{ marginLeft: 10 }}>
                <Text style={styles.activityText}>Foto capturada ({snapshotCamera})</Text>
                <Text style={styles.time}>{alertTime}</Text>
              </View>
            </View>

            <View style={styles.imageRow}>
              <Image source={{ uri: 'https://picsum.photos/200/120' }} style={styles.snapshotImage} />
              <Image source={{ uri: 'https://picsum.photos/201/120' }} style={styles.snapshotImage} />
            </View>
          </View>

          <Text style={styles.sectionTitle}>Familia e Cuidadores</Text>

          <View style={styles.caregivers}>
            <View style={styles.person}>
              <Image source={{ uri: 'https://i.pravatar.cc/101' }} style={styles.personImage} />
              <Text style={styles.personName}>Maria</Text>
            </View>

            <View style={styles.person}>
              <Image source={{ uri: 'https://i.pravatar.cc/102' }} style={styles.personImage} />
              <Text style={styles.personName}>David</Text>
            </View>

            <Pressable style={({ pressed }) => [styles.addPerson, pressed && styles.pressed]}>
              <Text style={styles.addPersonIcon}>+</Text>
              <Text style={styles.addPersonText}>Adicionar</Text>
            </Pressable>
          </View>

          {isLoading ? (
            <View style={styles.activityCard}>
              <ActivityIndicator color="#00A8CC" />
              <Text style={[styles.mutedText, { marginLeft: 10, marginTop: 0 }]}>Sincronizando cameras...</Text>
            </View>
          ) : null}
        </ScrollView>
      </View>
    </LayoutWithNavbar>
  );
}
