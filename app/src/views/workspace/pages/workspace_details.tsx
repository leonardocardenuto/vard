import { Feather, Ionicons } from '@expo/vector-icons';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Image,
  Linking,
  Modal,
  Pressable,
  RefreshControl,
  ScrollView,
  Switch,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { useVideoPlayer, VideoView } from 'expo-video';
import { WebView } from 'react-native-webview';

import { LayoutWithNavbar } from '../../../components/LayoutWithNavbar';
import { ApiRequestError, CameraResponse, listCameras, startCameraHlsStream, getWorkspaceFallAlert } from '../../../lib/api';
import { WorkspaceFallAlert, WorkspaceStackParamList } from '../types/workspace';
import { styles } from '../styles/workspace_details';

type Props = NativeStackScreenProps<WorkspaceStackParamList, 'WorkspaceDetails'>;
type CameraLiveViewProps = NativeStackScreenProps<WorkspaceStackParamList, 'CameraLiveView'>;

const CAMERA_WEBVIEW_INJECTED_JS = `
  (function() {
    function applyFullscreenStyles() {
      try {
        var style = document.getElementById('vard-camera-fullscreen-style');
        if (!style) {
          style = document.createElement('style');
          style.id = 'vard-camera-fullscreen-style';
          style.innerHTML = [
            'html, body { margin: 0 !important; padding: 0 !important; width: 100% !important; height: 100% !important; overflow: hidden !important; background: #000 !important; }',
            'iframe, video, img, canvas, object, embed { width: 100% !important; height: 100% !important; max-width: 100% !important; max-height: 100% !important; object-fit: contain !important; display: block !important; margin: 0 !important; padding: 0 !important; }'
          ].join('');
          document.head.appendChild(style);
        }
      } catch (error) {}
    }
    applyFullscreenStyles();
    setTimeout(applyFullscreenStyles, 300);
    setTimeout(applyFullscreenStyles, 1000);
  })();
  true;
`;

type FamilyMember = {
  id: string;
  name: string;
  phone: string;
  role: 'admin' | 'member' | 'caregiver' | 'viewer';
  avatarUrl: string;
};

export default function WorkspaceDetailsScreen({ navigation, route }: Props) {
  const { accessToken, workspace, fallAlert } = route.params;
  const [cameras, setCameras] = useState<CameraResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [isOpeningCameraId, setIsOpeningCameraId] = useState<string | null>(null);
  const [familyMembers, setFamilyMembers] = useState<FamilyMember[]>(() => seedFamilyMembers());
  const [isMemberActionOpen, setIsMemberActionOpen] = useState(false);
  const [selectedMember, setSelectedMember] = useState<FamilyMember | null>(null);
  const [isAddMemberOpen, setIsAddMemberOpen] = useState(false);
  const [newMemberPhone, setNewMemberPhone] = useState('');
  const [isFallAlertActive, setIsFallAlertActive] = useState(fallAlert?.active ?? false);

  useEffect(() => {
    setIsFallAlertActive(fallAlert?.active ?? false);
  }, [fallAlert]);

  // poll backend for fall alerts every 5s while on this screen
  useEffect(() => {
    let mounted = true;
    const interval = setInterval(async () => {
      try {
        const alert = await getWorkspaceFallAlert(accessToken, workspace.id);
        if (!mounted) return;
        setIsFallAlertActive(!!alert.active);
      } catch {
        // ignore
      }
    }, 5000);

    // initial fetch
    void (async () => {
      try {
        const alert = await getWorkspaceFallAlert(accessToken, workspace.id);
        if (mounted) setIsFallAlertActive(!!alert.active);
      } catch {
        // ignore
      }
    })();

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [accessToken, workspace.id]);

  const loadWorkspaceDetails = useCallback(async () => {
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
  }, [accessToken, workspace.id]);

  useEffect(() => {
    void loadWorkspaceDetails();
  }, [loadWorkspaceDetails]);

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      await loadWorkspaceDetails();
    } finally {
      setIsRefreshing(false);
    }
  }, [loadWorkspaceDetails]);

  const mainCamera = cameras[0];
  const secondCamera = cameras[1];
  const roomName = fallAlert?.roomName?.trim() || mainCamera?.name || 'Quarto';
  const alertTime = useMemo(() => formatAlertTime(fallAlert), [fallAlert]);
  const ambulancePhoneNumber = normalizeAmbulancePhoneNumber(fallAlert?.ambulancePhoneNumber);
  const roomCards = useMemo(() => buildRoomCards(cameras), [cameras]);

  async function handleAcknowledgeAlert() {
    Alert.alert(
      'Alerta registrado',
      'O sistema recebeu a confirmação de que a queda está sendo verificada.'
    );
  }

  async function handleCallAmbulance() {//ainda fazer para mandar para o aplicativo de ligação do celular com o numero preenchido
    
    const url = `tel:${ambulancePhoneNumber}`;

    try {
      const canOpen = await Linking.canOpenURL(url);
      if (!canOpen) {
        Alert.alert('Ligacao indisponivel', `Nao foi possivel abrir a ligacao para ${ambulancePhoneNumber}.`);
        return;
      }

      await Linking.openURL(url);
    } catch {
      Alert.alert('Erro ao ligar', `Nao foi possivel iniciar a chamada para ${ambulancePhoneNumber}.`);
    }
  }

  async function handleOpenRoomCamera(camera: CameraResponse) {
    if (isOpeningCameraId) {
      return;
    }

    setIsOpeningCameraId(camera.id);

    try {
      if (camera.connection_type === 'local-webview' || camera.connection_type === 'https') {
        navigation.navigate('CameraLiveView', {
          cameraName: camera.name,
          protocol: 'local-webview',
          url: camera.stream_url,
        });
        return;
      }

      const response = await startCameraHlsStream(accessToken, camera.id);
      navigation.navigate('CameraLiveView', {
        cameraName: camera.name,
        protocol: 'hls',
        url: response.playlist_url,
      });
    } catch (error) {
      Alert.alert(
        'Nao foi possivel abrir a camera',
        error instanceof ApiRequestError ? error.message : 'Tente novamente em instantes.'
      );
    } finally {
      setIsOpeningCameraId(null);
    }
  }

  function openMemberActions(member: FamilyMember) {
    setSelectedMember(member);
    setIsMemberActionOpen(true);
  }

  function closeMemberActions() {
    setSelectedMember(null);
    setIsMemberActionOpen(false);
  }

  function handlePromoteMember() {
    if (!selectedMember) {
      return;
    }

    setFamilyMembers((current) =>
      current.map((member) =>
        member.id === selectedMember.id
          ? { ...member, role: member.role === 'admin' ? 'member' : 'admin' }
          : member
      )
    );
    closeMemberActions();
    Alert.alert('Permissao atualizada', `${selectedMember.name} agora pode administrar o espaco.`);
  }

  function handleRemoveMember() {
    if (!selectedMember) {
      return;
    }

    setFamilyMembers((current) => current.filter((member) => member.id !== selectedMember.id));
    closeMemberActions();
    Alert.alert('Membro removido', `${selectedMember.name} foi removido da familia.`);
  }

  function handleAddMember() {
    const trimmedPhone = normalizeMemberPhoneNumber(newMemberPhone);

    if (!trimmedPhone) {
      Alert.alert('Informe o numero', 'Digite o numero do membro para adicionar.');
      return;
    }

    const phoneLabel = formatPhoneLabel(trimmedPhone);

    setFamilyMembers((current) => [
      {
        id: `member-${Date.now()}`,
        name: phoneLabel,
        phone: trimmedPhone,
        role: 'member',
        avatarUrl: `https://i.pravatar.cc/150?img=${Math.max(1, current.length + 3)}`,
      },
      ...current,
    ]);
    setNewMemberPhone('');
    setIsAddMemberOpen(false);
    Alert.alert('Convite pronto', `O membro ${phoneLabel} foi preparado para integração futura.`);
  }

  return (
    <LayoutWithNavbar>
      <View style={styles.container}>
        <ScrollView
          contentContainerStyle={styles.content}
          refreshControl={
            <RefreshControl
              colors={['#019BDE']}
              onRefresh={handleRefresh}
              refreshing={isRefreshing}
              tintColor="#019BDE"
            />
          }
          showsVerticalScrollIndicator={false}
        >
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

          <View style={[styles.alertCard, !isFallAlertActive && styles.alertCardSafe]}>
            <View style={styles.alertHeader}>
              <Ionicons
                color={isFallAlertActive ? '#C0392B' : '#0E7490'}
                name={isFallAlertActive ? 'warning' : 'shield-checkmark'}
                size={24}
              />
              <View style={{ marginLeft: 10 }}>
                <Text style={[styles.alertTitle, !isFallAlertActive && styles.alertTitleSafe]}>
                  {isFallAlertActive ? 'QUEDA DETECTADA' : 'NENHUMA QUEDA DETECTADA'}
                </Text>
                <Text style={styles.alertSubtitle}>{roomName} - {alertTime}</Text>
              </View>
            </View>

            <View style={styles.alertToggleRow}>
              <View style={styles.alertToggleTextWrap}>
                <Text style={styles.alertToggleTitle}>Teste de detecção</Text>
                <Text style={styles.alertToggleSubtitle}>
                  Ative para simular um evento de queda e desative para ver o estado seguro.
                </Text>
              </View>

              <Switch
                value={isFallAlertActive}
                onValueChange={setIsFallAlertActive}
                trackColor={{ false: '#B2F0FA', true: '#FFB4AA' }}
                thumbColor={isFallAlertActive ? '#C0392B' : '#0E7490'}
              />
            </View>

            {isFallAlertActive ? (
              <>
                <TouchableOpacity onPress={handleAcknowledgeAlert} style={styles.secondaryButton}>
                  <Text style={styles.secondaryText}>Já estou verificando!</Text>
                </TouchableOpacity>

                <TouchableOpacity onPress={handleCallAmbulance} style={styles.primaryButton}>
                  <Text style={styles.primaryText}>Chamar ambulância</Text>
                </TouchableOpacity>
              </>
            ) : (
              <View style={styles.safeStateBox}>
                <Text style={styles.safeStateText}>Nenhuma ocorrência de queda.</Text>
              </View>
            )}
          </View>

          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Atividade Recente</Text>
          </View>

          <View style={styles.snapshotCard}>
            <View style={styles.snapshotHeader}>
              <Ionicons color="#00A8CC" name="camera-outline" size={24} />
              <View style={{ marginLeft: 10 }}>
                <Text style={styles.activityText}>Cômodos monitorados</Text>
                <Text style={styles.time}>{roomCards.length} ambiente(s) conectado(s)</Text>
              </View>
            </View>

            <View style={styles.roomsGrid}>
              {roomCards.length > 0 ? (
                roomCards.map((room) => (
                  <Pressable
                    key={room.id}
                    disabled={isOpeningCameraId === room.id}
                    onPress={() => handleOpenRoomCamera(room.camera)}
                    style={({ pressed }) => [styles.roomCard, pressed && styles.pressed]}
                  >
                    <Image source={{ uri: room.imageUrl }} style={styles.roomImage} />
                    <View style={styles.roomContent}>
                      <Text numberOfLines={1} style={styles.roomName}>
                        {room.name}
                      </Text>
                      <Text numberOfLines={1} style={styles.roomMeta}>
                        {isOpeningCameraId === room.id ? 'Abrindo camera...' : room.updatedAtLabel}
                      </Text>
                    </View>
                  </Pressable>
                ))
              ) : (
                <View style={styles.roomContent}>
                  <Text style={styles.roomName}>Nenhum cômodo disponível</Text>
                  <Text style={styles.roomMeta}>Aguarde o backend enviar as imagens dos ambientes.</Text>
                </View>
              )}
            </View>
          </View>

          <View style={styles.familyHeaderRow}>
            <Text style={styles.sectionTitle}>Familia e Cuidadores</Text>
            <Text style={styles.familySubtitle}>Segure um membro para gerenciar permissoes</Text>
          </View>

          <View style={styles.caregivers}>
            {familyMembers.map((member) => (
              <Pressable
                key={member.id}
                accessibilityRole="button"
                delayLongPress={250}
                onLongPress={() => openMemberActions(member)}
                style={({ pressed }) => [styles.person, pressed && styles.pressed]}
              >
                <Image source={{ uri: member.avatarUrl }} style={styles.personImage} />
                <Text numberOfLines={1} style={styles.personName}>
                  {member.name}
                </Text>
                <Text style={styles.memberRole}>{member.role}</Text>
              </Pressable>
            ))}

            <Pressable
              accessibilityRole="button"
              onPress={() => setIsAddMemberOpen(true)}
              style={({ pressed }) => [styles.addPerson, pressed && styles.pressed]}
            >
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

        <Modal animationType="fade" transparent visible={isMemberActionOpen} onRequestClose={closeMemberActions}>
          <Pressable onPress={closeMemberActions} style={styles.modalOverlay}>
            <Pressable onPress={() => undefined} style={styles.modalCard}>
              <Text style={styles.modalTitle}>{selectedMember?.name ?? 'Membro'}</Text>
              <Text style={styles.modalSubtitle}>Escolha a acao que deseja aplicar.</Text>

              <Pressable onPress={handlePromoteMember} style={styles.modalActionButton}>
                <Text style={styles.modalActionText}>Tornar admin</Text>
              </Pressable>

              <Pressable onPress={handleRemoveMember} style={[styles.modalActionButton, styles.modalDangerButton]}>
                <Text style={[styles.modalActionText, styles.modalDangerText]}>Remover membro</Text>
              </Pressable>

              <Pressable onPress={closeMemberActions} style={styles.modalCancelButton}>
                <Text style={styles.modalCancelText}>Cancelar</Text>
              </Pressable>
            </Pressable>
          </Pressable>
        </Modal>

        <Modal animationType="slide" transparent visible={isAddMemberOpen} onRequestClose={() => setIsAddMemberOpen(false)}>
          <Pressable onPress={() => setIsAddMemberOpen(false)} style={styles.modalOverlay}>
            <Pressable onPress={() => undefined} style={styles.modalCard}>
              <Text style={styles.modalTitle}>Adicionar membro</Text>
              <Text style={styles.modalSubtitle}>Informe o numero de telefone para preparar o convite.</Text>

              <TextInput
                keyboardType="phone-pad"
                onChangeText={setNewMemberPhone}
                placeholder="(11) 99999-9999"
                placeholderTextColor="#98A2B3"
                style={styles.modalInput}
                value={newMemberPhone}
              />

              <Pressable onPress={handleAddMember} style={styles.modalActionButton}>
                <Text style={styles.modalActionText}>Adicionar</Text>
              </Pressable>

              <Pressable onPress={() => setIsAddMemberOpen(false)} style={styles.modalCancelButton}>
                <Text style={styles.modalCancelText}>Cancelar</Text>
              </Pressable>
            </Pressable>
          </Pressable>
        </Modal>
      </View>
    </LayoutWithNavbar>
  );
}

export function WorkspaceCameraLiveViewScreen({ navigation, route }: CameraLiveViewProps) {
  const { cameraName, protocol, url } = route.params;
  const player = useVideoPlayer(null);

  useEffect(() => {
    async function syncPlayerSource() {
      if (protocol !== 'hls') {
        return;
      }

      try {
        await player.replaceAsync(url);
        player.play();
      } catch {
        // streaming errors are surfaced by the backend/source
      }
    }

    void syncPlayerSource();
  }, [player, protocol, url]);

  return (
    <LayoutWithNavbar>
      <ScrollView contentContainerStyle={styles.cameraLiveContent} showsVerticalScrollIndicator={false}>
        <View style={styles.cameraLiveTopSpacer} />

        <View style={styles.cameraLiveHeaderRow}>
          <Pressable onPress={() => navigation.goBack()} style={styles.backButton}>
            <Feather color="#111827" name="chevron-left" size={20} />
          </Pressable>
          <View style={styles.cameraLiveHeaderText}>
            <Text numberOfLines={1} style={styles.cameraLiveTitle}>
              {cameraName}
            </Text>
            <Text style={styles.cameraLiveSubtitle}>Camera ao vivo</Text>
          </View>
        </View>

        <View style={styles.cameraLiveViewerCard}>
          {protocol === 'local-webview' ? (
            <WebView
              injectedJavaScript={CAMERA_WEBVIEW_INJECTED_JS}
              injectedJavaScriptBeforeContentLoaded={CAMERA_WEBVIEW_INJECTED_JS}
              javaScriptEnabled
              scalesPageToFit={false}
              source={{ uri: url }}
              startInLoadingState
              style={styles.cameraLiveWebview}
            />
          ) : (
            <VideoView contentFit="cover" nativeControls player={player} style={styles.cameraLiveVideo} />
          )}
        </View>
      </ScrollView>
    </LayoutWithNavbar>
  );
}

function formatAlertTime(fallAlert?: WorkspaceFallAlert) {
  if (fallAlert?.occurredAt) {
    const parsedDate = new Date(fallAlert.occurredAt);
    if (!Number.isNaN(parsedDate.getTime())) {
      return parsedDate.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    }
  }

  return new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

function normalizeAmbulancePhoneNumber(value?: string) {
  const normalized = value?.trim();
  return normalized || '192';
}

function normalizeMemberPhoneNumber(value: string) {
  return value.replace(/\s+/g, ' ').trim();
}

function formatPhoneLabel(phone: string) {
  const digits = phone.replace(/\D/g, '');
  if (!digits) {
    return 'Novo membro';
  }

  return digits.length >= 11 ? `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7, 11)}` : phone;
}

function seedFamilyMembers(): FamilyMember[] {
  return [
    {
      id: 'member-1',
      name: 'Maria',
      phone: '(11) 98888-1111',
      role: 'admin',
      avatarUrl: 'https://i.pravatar.cc/101',
    },
    {
      id: 'member-2',
      name: 'David',
      phone: '(11) 97777-2222',
      role: 'caregiver',
      avatarUrl: 'https://i.pravatar.cc/102',
    },
  ];
}

function buildRoomCards(cameras: CameraResponse[]) {
  return cameras.map((camera, index) => ({
    id: camera.id,
    camera,
    name: camera.name || `Cômodo ${index + 1}`,
    imageUrl: camera.room_image_url || defaultRoomImageForIndex(index),
    updatedAtLabel: camera.updated_at
      ? `Atualizado em ${new Date(camera.updated_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`
      : 'Imagem recebida do backend',
  }));
}

function defaultRoomImageForIndex(index: number) {
  return `https://picsum.photos/seed/vard-room-${index + 1}/480/300`;
}
