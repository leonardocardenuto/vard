import { Feather } from '@expo/vector-icons';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useVideoPlayer, VideoView } from 'expo-video';
import * as FileSystem from 'expo-file-system/legacy';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Clipboard,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  Text,
  TextInput,
  View,
} from 'react-native';
import { LayoutWithNavbar } from '../../../components/LayoutWithNavbar';
import {
  ApiRequestError,
  CameraResponse,
  FallEventResponse,
  NotificationResponse,
  autoConfigureCamera,
  createInvite,
  deleteCamera,
  getFallEventClip,
  getCameraMjpegUrl,
  getMe,
  listCameras,
  listFallEvents,
  listNotifications,
  listWorkspaceMembers,
  startCameraHlsStream,
} from '../../../lib/api';
import { decryptFallClip } from '../../../lib/fallHistoryCrypto';
import { CameraLiveViewScreen as CameraHistoryLiveViewScreen } from '../../settings/pages/CameraLiveViewScreen';
import { WorkspaceFeedback, WorkspaceFeedbackModal } from '../components/WorkspaceFeedbackModal';
import { SettingsStackParamList } from '../../settings/types';
import { WorkspaceStackParamList } from '../types/workspace';
import { styles } from '../styles/workspace_details';

type Props = NativeStackScreenProps<WorkspaceStackParamList, 'WorkspaceDetails'>;
type CameraLiveViewProps = NativeStackScreenProps<WorkspaceStackParamList, 'CameraLiveView'>;
type CameraOccurrencesProps = NativeStackScreenProps<WorkspaceStackParamList, 'CameraOccurrences'>;

type FamilyMember = {
  id: string;
  contact: string;
  role: 'admin' | 'member' | 'caregiver' | 'viewer';
};

type CameraFormMode = 'create' | 'edit';

type CameraProtocol =
  | 'http-auto'
  | 'https-manual'
  | 'local-agent-webcam'
  | 'local-webview'
  | 'rtsp-auto'
  | 'rtsp-manual';

type CameraFormState = {
  host: string;
  password: string;
  username: string;
};

type MemberRole = FamilyMember['role'];

const initialCameraForm: CameraFormState = {
  host: '',
  password: '',
  username: '',
};

const memberRoleOptions: Array<{ label: string; value: MemberRole }> = [
  { label: 'Membro', value: 'member' },
  { label: 'Administrador', value: 'admin' },
  { label: 'Visualizador', value: 'viewer' },
];

export default function WorkspaceDetailsScreen({ navigation, route }: Props) {
  const { accessToken, workspace } = route.params;
  const [cameras, setCameras] = useState<CameraResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [isOpeningCameraId, setIsOpeningCameraId] = useState<string | null>(null);
  const [familyMembers, setFamilyMembers] = useState<FamilyMember[]>([]);
  const [isMemberActionOpen, setIsMemberActionOpen] = useState(false);
  const [selectedMember, setSelectedMember] = useState<FamilyMember | null>(null);
  const [isAddMemberOpen, setIsAddMemberOpen] = useState(false);
  const [newMemberEmail, setNewMemberEmail] = useState('');
  const [newMemberRole, setNewMemberRole] = useState<MemberRole>('member');
  const [isInvitingMember, setIsInvitingMember] = useState(false);
  const [generatedInviteCode, setGeneratedInviteCode] = useState('');
  const [isInviteCodeCopied, setIsInviteCodeCopied] = useState(false);
  const [cameraFormMode, setCameraFormMode] = useState<CameraFormMode>('create');
  const [cameraForm, setCameraForm] = useState<CameraFormState>(initialCameraForm);
  const [cameraFormError, setCameraFormError] = useState('');
  const [isCameraFormOpen, setIsCameraFormOpen] = useState(false);
  const [isSavingCamera, setIsSavingCamera] = useState(false);
  const [editingCamera, setEditingCamera] = useState<CameraResponse | null>(null);
  const [cameraToDelete, setCameraToDelete] = useState<CameraResponse | null>(null);
  const [isDeletingCamera, setIsDeletingCamera] = useState(false);
  const [feedback, setFeedback] = useState<WorkspaceFeedback | null>(null);

  const loadWorkspaceDetails = useCallback(async () => {
    try {
      setErrorMessage('');
      setIsLoading(true);
      const [workspaceCameras, workspaceMembers] = await Promise.all([
        listCameras(accessToken, workspace.id),
        listWorkspaceMembers(accessToken, workspace.id),
      ]);
      setCameras(workspaceCameras);
      setFamilyMembers(workspaceMembers.map((member) => ({
        id: member.user_id,
        contact: member.email,
        role: member.role,
      })));
    } catch (error) {
      setErrorMessage(
        error instanceof ApiRequestError ? error.message : 'Não foi possível carregar os detalhes.'
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

  const roomCards = useMemo(() => buildRoomCards(cameras), [cameras]);

  async function handleOpenRoomCamera(camera: CameraResponse) {
    if (isOpeningCameraId) {
      return;
    }

    setIsOpeningCameraId(camera.id);

    try {
      if ((camera.metadata ?? camera.metadata_json ?? {}).protocol === 'local-agent-webcam') {
        navigation.navigate('CameraLiveView', {
          cameraName: camera.name,
          protocol: 'agent-mjpeg',
          url: getCameraMjpegUrl(camera.id),
          accessToken,
          cameraId: camera.id,
          workspaceId: workspace.id,
        });
        return;
      }
      if (camera.connection_type === 'local-webview' || camera.connection_type === 'https') {
        navigation.navigate('CameraLiveView', {
          cameraName: camera.name,
          protocol: 'local-webview',
          url: camera.stream_url,
          cameraId: camera.id,
          workspaceId: workspace.id,
        });
        return;
      }

      const response = await startCameraHlsStream(accessToken, camera.id);
      navigation.navigate('CameraLiveView', {
        cameraName: camera.name,
        protocol: 'hls',
        url: response.playlist_url,
        cameraId: camera.id,
        workspaceId: workspace.id,
      });
    } catch (error) {
      setFeedback({
        title: 'Não foi possível abrir a câmera',
        message: error instanceof ApiRequestError ? error.message : 'Tente novamente em instantes.',
        tone: 'error',
      });
    } finally {
      setIsOpeningCameraId(null);
    }
  }

  function handleOpenCameraOccurrences(camera: CameraResponse) {
    navigation.navigate('CameraOccurrences', {
      accessToken,
      cameraId: camera.id,
      cameraName: camera.name,
      workspaceId: workspace.id,
    });
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
    const memberLabel = getMemberLabel(selectedMember);
    closeMemberActions();
    setFeedback({
      title: 'Permissão atualizada',
      message: `${memberLabel} agora está como ${formatMemberRole(
        selectedMember.role === 'admin' ? 'member' : 'admin'
      ).toLowerCase()}.`,
      tone: 'success',
    });
  }

  function handleRemoveMember() {
    if (!selectedMember) {
      return;
    }

    const memberLabel = getMemberLabel(selectedMember);
    setFamilyMembers((current) => current.filter((member) => member.id !== selectedMember.id));
    closeMemberActions();
    setFeedback({
      title: 'Membro removido',
      message: `${memberLabel} foi removido da família.`,
      tone: 'success',
    });
  }

  function openCreateCameraForm() {
    setCameraFormMode('create');
    setEditingCamera(null);
    setCameraForm(initialCameraForm);
    setCameraFormError('');
    setIsCameraFormOpen(true);
  }

  function openEditCameraForm(camera: CameraResponse) {
    const metadata = getCameraMetadata(camera);
    const parsedConnection = parseCameraConnection(camera);
    setCameraFormMode('edit');
    setEditingCamera(camera);
    setCameraForm({
      host: firstString(metadata.host, parsedConnection.host),
      password: '',
      username: firstString(metadata.username, parsedConnection.username),
    });
    setCameraFormError('');
    setIsCameraFormOpen(true);
  }

  function closeCameraForm() {
    if (isSavingCamera) {
      return;
    }
    setIsCameraFormOpen(false);
    setEditingCamera(null);
    setCameraFormError('');
  }

  function updateCameraFormField(field: keyof CameraFormState, value: string) {
    setCameraForm((current) => ({
      ...current,
      [field]: value,
    }));
    setCameraFormError('');
  }

  async function handleSaveCamera() {
    if (isSavingCamera) {
      return;
    }

    const host = cameraForm.host.trim();
    const username = cameraForm.username.trim();
    if (!host || !username || !cameraForm.password) {
      setCameraFormError('Preencha host, nome de usuário e senha.');
      return;
    }

    setIsSavingCamera(true);
    setCameraFormError('');
    try {
      const configuredCamera = await autoConfigureCamera(
        accessToken,
        {
          workspace_id: workspace.id,
          host,
          username,
          password: cameraForm.password,
        },
        cameraFormMode === 'edit' ? editingCamera?.id : undefined
      );
      if (cameraFormMode === 'edit' && editingCamera) {
        setCameras((current) =>
          current.map((camera) => (camera.id === configuredCamera.id ? configuredCamera : camera))
        );
      } else {
        setCameras((current) => [configuredCamera, ...current]);
      }
      setIsCameraFormOpen(false);
      setEditingCamera(null);
    } catch (error) {
      setCameraFormError(
        error instanceof ApiRequestError
          ? error.message
          : 'Não foi possível detectar uma câmera nesse host.'
      );
    } finally {
      setIsSavingCamera(false);
    }
  }

  function closeDeleteCameraConfirmation() {
    if (isDeletingCamera) {
      return;
    }
    setCameraToDelete(null);
  }

  async function handleDeleteCamera() {
    if (!cameraToDelete || isDeletingCamera) {
      return;
    }

    const camera = cameraToDelete;
    setIsDeletingCamera(true);
    try {
      await deleteCamera(accessToken, camera.id);
      setCameras((current) => current.filter((currentCamera) => currentCamera.id !== camera.id));
      setCameraToDelete(null);
      setFeedback({
        title: 'Câmera excluída',
        message: `${camera.name} foi removida deste espaço.`,
        tone: 'success',
      });
    } catch (error) {
      setFeedback({
        title: 'Não foi possível excluir a câmera',
        message: error instanceof ApiRequestError ? error.message : 'Tente novamente em instantes.',
        tone: 'error',
      });
    } finally {
      setIsDeletingCamera(false);
    }
  }

  async function handleAddMember() {
    if (isInvitingMember) {
      return;
    }

    const trimmedEmail = newMemberEmail.trim().toLowerCase();

    if (!trimmedEmail) {
      setFeedback({
        title: 'Informe o e-mail',
        message: 'Digite o e-mail do membro para gerar o convite.',
        tone: 'warning',
      });
      return;
    }

    setIsInvitingMember(true);
    try {
      const invite = await createInvite(accessToken, {
        workspace_id: workspace.id,
        email: trimmedEmail,
        role: newMemberRole,
      });

      setFamilyMembers((current) => [
        {
          id: `member-${Date.now()}`,
          contact: trimmedEmail,
          role: newMemberRole,
        },
        ...current,
      ]);
      setGeneratedInviteCode(invite.token);
      setIsInviteCodeCopied(false);
      setNewMemberEmail('');
      setNewMemberRole('member');
    } catch (error) {
      setFeedback({
        title: 'Não foi possível gerar o código',
        message: error instanceof ApiRequestError ? error.message : 'Tente novamente em instantes.',
        tone: 'error',
      });
    } finally {
      setIsInvitingMember(false);
    }
  }

  function handleCopyInviteCode() {
    if (!generatedInviteCode) {
      return;
    }

    Clipboard.setString(generatedInviteCode);
    setIsInviteCodeCopied(true);
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
            <View style={styles.headerTitleWrap}>
              <Text numberOfLines={1} style={styles.title}>{workspace.name}</Text>
            </View>
          </View>

          <View style={styles.workspaceMetrics}>
            <View style={styles.metricPill}>
              <Feather color="#00326D" name="camera" size={15} />
              <Text style={styles.metricText}>{cameras.length} câmeras</Text>
            </View>
            <View style={styles.metricPill}>
              <Feather color="#00326D" name="users" size={15} />
              <Text style={styles.metricText}>
                {familyMembers.length} {familyMembers.length === 1 ? 'membro' : 'membros'}
              </Text>
            </View>
          </View>

          {errorMessage ? <Text style={styles.errorText}>{errorMessage}</Text> : null}

          <View style={styles.sectionHeader}>
            <View>
              <Text style={styles.sectionTitle}>Câmeras cadastradas</Text>
              <Text style={styles.sectionSubtitle}>Organize nome, local e conexão de cada câmera.</Text>
            </View>
            <Pressable
              accessibilityRole="button"
              onPress={openCreateCameraForm}
              style={({ pressed }) => [styles.sectionActionButton, pressed && styles.pressed]}
            >
              <Feather color="#00326D" name="plus" size={16} />
              <Text style={styles.sectionActionText}>Adicionar</Text>
            </Pressable>
          </View>

          <View style={styles.cameraList}>
            {roomCards.length > 0 ? (
              roomCards.map((room) => (
                <View key={room.id} style={styles.cameraRow}>
                  <Pressable
                    accessibilityRole="button"
                    disabled={isOpeningCameraId === room.id}
                    onPress={() => handleOpenRoomCamera(room.camera)}
                    style={({ pressed }) => [styles.cameraRowMain, pressed && styles.pressed]}
                  >
                    <View style={styles.cameraIconBox}>
                      <Feather color="#00326D" name="video" size={19} />
                    </View>
                    <View style={styles.cameraInfo}>
                      <Text numberOfLines={1} style={styles.cameraName}>{room.name}</Text>
                      <Text numberOfLines={1} style={styles.cameraMeta}>
                        {room.location} · {room.connectionLabel}
                      </Text>
                    </View>
                    <View style={[
                      styles.cameraStatusDot,
                      room.camera.status === 'online' && styles.cameraStatusDotOnline,
                    ]} />
                  </Pressable>

                  <View style={styles.cameraRowActions}>
                    <Pressable
                      accessibilityRole="button"
                      onPress={() => handleOpenRoomCamera(room.camera)}
                      style={({ pressed }) => [styles.cameraInlineAction, pressed && styles.pressed]}
                    >
                      <Feather color="#00326D" name="play-circle" size={15} />
                      <Text style={styles.cameraInlineActionText}>Ao vivo</Text>
                    </Pressable>
                    <Pressable
                      accessibilityRole="button"
                      onPress={() => handleOpenCameraOccurrences(room.camera)}
                      style={({ pressed }) => [styles.cameraInlineAction, pressed && styles.pressed]}
                    >
                      <Feather color="#00326D" name="alert-circle" size={15} />
                      <Text style={styles.cameraInlineActionText}>Ocorrências</Text>
                    </Pressable>
                    <Pressable
                      accessibilityLabel={`Editar câmera ${room.name}`}
                      accessibilityRole="button"
                      onPress={() => openEditCameraForm(room.camera)}
                      style={({ pressed }) => [styles.cameraInlineAction, pressed && styles.pressed]}
                    >
                      <Feather color="#475467" name="edit-2" size={15} />
                      <Text style={styles.cameraInlineActionText}>Editar</Text>
                    </Pressable>
                    <Pressable
                      accessibilityLabel={`Excluir câmera ${room.name}`}
                      accessibilityRole="button"
                      onPress={() => setCameraToDelete(room.camera)}
                      style={({ pressed }) => [
                        styles.cameraInlineAction,
                        styles.cameraInlineDangerAction,
                        pressed && styles.pressed,
                      ]}
                    >
                      <Feather color="#B42318" name="trash-2" size={15} />
                      <Text style={[styles.cameraInlineActionText, styles.cameraInlineDangerActionText]}>
                        Excluir
                      </Text>
                    </Pressable>
                  </View>
                </View>
              ))
            ) : (
              <View style={styles.emptyCameraState}>
                <View style={styles.cameraIconBox}>
                  <Feather color="#00326D" name="video" size={19} />
                </View>
                <View style={styles.emptyCameraCopy}>
                  <Text style={styles.cameraName}>Nenhuma câmera cadastrada</Text>
                  <Text style={styles.cameraMeta}>Adicione uma câmera para iniciar o monitoramento.</Text>
                </View>
                <Pressable
                  accessibilityRole="button"
                  onPress={openCreateCameraForm}
                  style={({ pressed }) => [styles.emptyCameraButton, pressed && styles.pressed]}
                >
                  <Feather color="#FFFFFF" name="plus" size={16} />
                </Pressable>
              </View>
            )}
          </View>

          <View style={styles.sectionHeader}>
            <View>
              <Text style={styles.sectionTitle}>Membros</Text>
              <Text style={styles.sectionSubtitle}>Convites por código para acesso manual.</Text>
            </View>
            <Pressable
              accessibilityRole="button"
              onPress={() => {
                setGeneratedInviteCode('');
                setIsAddMemberOpen(true);
              }}
              style={({ pressed }) => [styles.sectionActionButton, pressed && styles.pressed]}
            >
              <Feather color="#00326D" name="user-plus" size={16} />
              <Text style={styles.sectionActionText}>Convidar</Text>
            </Pressable>
          </View>

          <View style={styles.memberList}>
            {familyMembers.map((member) => (
              <Pressable
                key={member.id}
                accessibilityRole="button"
                onPress={() => openMemberActions(member)}
                style={({ pressed }) => [styles.memberRow, pressed && styles.pressed]}
              >
                <View style={styles.memberAvatarPlaceholder}>
                  <Feather color="#00326D" name="mail" size={19} />
                </View>
                <View style={styles.memberInfo}>
                  <Text numberOfLines={1} style={styles.personName}>{member.contact}</Text>
                </View>
                <Text style={styles.memberRole}>{formatMemberRole(member.role)}</Text>
              </Pressable>
            ))}
          </View>

          {isLoading ? (
            <View style={styles.activityCard}>
              <ActivityIndicator color="#00A8CC" />
              <Text style={[styles.mutedText, { marginLeft: 10, marginTop: 0 }]}>Sincronizando câmeras...</Text>
            </View>
          ) : null}
        </ScrollView>

        <Modal animationType="fade" transparent visible={isCameraFormOpen} onRequestClose={closeCameraForm}>
          <Pressable onPress={closeCameraForm} style={styles.modalOverlay}>
            <KeyboardAvoidingView
              behavior={Platform.OS === 'ios' ? 'padding' : undefined}
              style={styles.keyboardModalWrap}
            >
              <Pressable onPress={() => undefined} style={styles.modalCard}>
                <Text style={styles.modalTitle}>
                  {cameraFormMode === 'edit' ? 'Editar câmera' : 'Adicionar câmera'}
                </Text>
                <Text style={styles.modalSubtitle}>
                  Informe os dados de acesso. O VARD testará a conexão e identificará o método automaticamente.
                </Text>

                <TextInput
                  autoCapitalize="none"
                  autoCorrect={false}
                  keyboardType="url"
                  onChangeText={(value) => updateCameraFormField('host', value)}
                  placeholder="Host ou IP da câmera"
                  placeholderTextColor="#98A2B3"
                  returnKeyType="next"
                  style={styles.modalInput}
                  value={cameraForm.host}
                />

                <TextInput
                  autoCapitalize="none"
                  autoCorrect={false}
                  onChangeText={(value) => updateCameraFormField('username', value)}
                  placeholder="Nome de usuário"
                  placeholderTextColor="#98A2B3"
                  returnKeyType="next"
                  style={styles.modalInput}
                  value={cameraForm.username}
                />

                <TextInput
                  autoCapitalize="none"
                  autoCorrect={false}
                  onChangeText={(value) => updateCameraFormField('password', value)}
                  placeholder="Senha"
                  placeholderTextColor="#98A2B3"
                  secureTextEntry
                  style={styles.modalInput}
                  value={cameraForm.password}
                />

                {cameraFormError ? <Text style={styles.errorText}>{cameraFormError}</Text> : null}

                <Pressable
                  disabled={isSavingCamera}
                  onPress={handleSaveCamera}
                  style={[styles.modalActionButton, isSavingCamera && styles.buttonDisabled]}
                >
                  <Text style={styles.modalActionText}>
                    {isSavingCamera
                      ? 'Testando conexão...'
                      : cameraFormMode === 'edit'
                        ? 'Testar e salvar'
                        : 'Detectar e adicionar'}
                  </Text>
                </Pressable>

                <Pressable onPress={closeCameraForm} style={styles.modalCancelButton}>
                  <Text style={styles.modalCancelText}>Cancelar</Text>
                </Pressable>
              </Pressable>
            </KeyboardAvoidingView>
          </Pressable>
        </Modal>

        <Modal
          animationType="fade"
          transparent
          visible={cameraToDelete !== null}
          onRequestClose={closeDeleteCameraConfirmation}
        >
          <Pressable onPress={closeDeleteCameraConfirmation} style={styles.modalOverlay}>
            <Pressable onPress={() => undefined} style={styles.modalCard}>
              <View style={styles.deleteCameraIcon}>
                <Feather color="#B42318" name="trash-2" size={24} />
              </View>
              <Text style={styles.modalTitle}>Excluir câmera?</Text>
              <Text style={styles.modalSubtitle}>
                {cameraToDelete
                  ? `${cameraToDelete.name} será removida deste espaço.`
                  : 'A câmera será removida deste espaço.'}
              </Text>

              <Pressable
                disabled={isDeletingCamera}
                onPress={() => void handleDeleteCamera()}
                style={[styles.modalActionButton, styles.modalDangerButton, isDeletingCamera && styles.buttonDisabled]}
              >
                {isDeletingCamera ? <ActivityIndicator color="#B42318" /> : null}
                <Text style={[styles.modalActionText, styles.modalDangerText]}>
                  {isDeletingCamera ? 'Excluindo...' : 'Excluir câmera'}
                </Text>
              </Pressable>

              <Pressable disabled={isDeletingCamera} onPress={closeDeleteCameraConfirmation} style={styles.modalCancelButton}>
                <Text style={styles.modalCancelText}>Cancelar</Text>
              </Pressable>
            </Pressable>
          </Pressable>
        </Modal>

        <Modal animationType="fade" transparent visible={isMemberActionOpen} onRequestClose={closeMemberActions}>
          <Pressable onPress={closeMemberActions} style={styles.modalOverlay}>
            <Pressable onPress={() => undefined} style={styles.modalCard}>
              <Text style={styles.modalTitle}>{selectedMember ? getMemberLabel(selectedMember) : 'Membro'}</Text>
              <Text style={styles.modalSubtitle}>Escolha a ação que deseja aplicar.</Text>

              <Pressable onPress={handlePromoteMember} style={styles.modalActionButton}>
                <Text style={styles.modalActionText}>
                  {selectedMember?.role === 'admin' ? 'Remover administrador' : 'Tornar administrador'}
                </Text>
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

        <Modal animationType="fade" transparent visible={isAddMemberOpen} onRequestClose={() => setIsAddMemberOpen(false)}>
          <Pressable onPress={() => setIsAddMemberOpen(false)} style={styles.modalOverlay}>
            <Pressable onPress={() => undefined} style={styles.modalCard}>
              <Text style={styles.modalTitle}>Gerar código de convite</Text>
              <Text style={styles.modalSubtitle}>
                Informe o e-mail que poderá usar o código. Depois envie o código manualmente para essa pessoa.
              </Text>

              <TextInput
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="email-address"
                onChangeText={setNewMemberEmail}
                placeholder="email@exemplo.com"
                placeholderTextColor="#98A2B3"
                style={styles.modalInput}
                testID="workspace-invite-email"
                value={newMemberEmail}
              />

              <View style={styles.rolePicker}>
                {memberRoleOptions.map((option) => {
                  const isSelected = newMemberRole === option.value;
                  return (
                    <Pressable
                      key={option.value}
                      onPress={() => setNewMemberRole(option.value)}
                      style={[styles.roleChip, isSelected && styles.roleChipSelected]}
                    >
                      <Text style={[styles.roleChipText, isSelected && styles.roleChipTextSelected]}>
                        {option.label}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>

              {generatedInviteCode ? (
                <Pressable
                  accessibilityHint="Copia o código de convite"
                  accessibilityLabel="Copiar código de convite"
                  accessibilityRole="button"
                  onPress={handleCopyInviteCode}
                  style={({ pressed }) => [styles.inviteCodeBox, pressed && styles.inviteCodeBoxPressed]}
                >
                  <View style={styles.inviteCodeHeader}>
                    <Text style={styles.inviteCodeLabel}>
                      {isInviteCodeCopied ? 'Código copiado!' : 'Toque para copiar'}
                    </Text>
                    <Feather
                      color={isInviteCodeCopied ? '#039855' : '#00326D'}
                      name={isInviteCodeCopied ? 'check' : 'copy'}
                      size={18}
                    />
                  </View>
                  <Text selectable style={styles.inviteCodeText} testID="workspace-invite-code-value">
                    {generatedInviteCode}
                  </Text>
                </Pressable>
              ) : null}

              <Pressable
                disabled={isInvitingMember}
                onPress={handleAddMember}
                style={[styles.modalActionButton, isInvitingMember && styles.buttonDisabled]}
              >
                <Text style={styles.modalActionText}>
                  {isInvitingMember ? 'Gerando...' : generatedInviteCode ? 'Gerar novo código' : 'Gerar código'}
                </Text>
              </Pressable>

              <Pressable
                onPress={() => {
                  setIsAddMemberOpen(false);
                  setGeneratedInviteCode('');
                  setIsInviteCodeCopied(false);
                }}
                style={styles.modalCancelButton}
              >
                <Text style={styles.modalCancelText}>{generatedInviteCode ? 'Concluir' : 'Cancelar'}</Text>
              </Pressable>
            </Pressable>
          </Pressable>
        </Modal>
        <WorkspaceFeedbackModal feedback={feedback} onClose={() => setFeedback(null)} />
      </View>
    </LayoutWithNavbar>
  );
}

export function WorkspaceCameraLiveViewScreen({ navigation, route }: CameraLiveViewProps) {
  return (
    <CameraHistoryLiveViewScreen
      {...({ navigation, route } as unknown as NativeStackScreenProps<SettingsStackParamList, 'CameraLiveView'>)}
    />
  );
}

export function WorkspaceCameraOccurrencesScreen({ navigation, route }: CameraOccurrencesProps) {
  const { accessToken, cameraId, cameraName, workspaceId } = route.params;
  const clipPlayer = useVideoPlayer(null);
  const [occurrences, setOccurrences] = useState<NotificationResponse[]>([]);
  const [fallEventsByNotificationId, setFallEventsByNotificationId] = useState<
    Record<string, FallEventResponse>
  >({});
  const [isLoadingOccurrences, setIsLoadingOccurrences] = useState(true);
  const [isRefreshingOccurrences, setIsRefreshingOccurrences] = useState(false);
  const [occurrencesError, setOccurrencesError] = useState('');
  const [loadingClipId, setLoadingClipId] = useState<string | null>(null);
  const [clipError, setClipError] = useState('');
  const [clipUri, setClipUri] = useState<string | null>(null);
  const [isClipVisible, setIsClipVisible] = useState(false);

  const loadOccurrences = useCallback(async () => {
    try {
      setOccurrencesError('');
      const [notifications, fallEvents] = await Promise.all([
        listNotifications(accessToken, workspaceId),
        listFallEvents(accessToken, workspaceId),
      ]);
      setOccurrences(notifications.filter((notification) => notification.camera_id === cameraId));
      setFallEventsByNotificationId(
        Object.fromEntries(
          fallEvents
            .filter((event) => event.camera_id === cameraId && event.notification_id)
            .map((event) => [event.notification_id as string, event])
        )
      );
    } catch (error) {
      setOccurrencesError(
        error instanceof ApiRequestError ? error.message : 'Não foi possível carregar as ocorrências.'
      );
    } finally {
      setIsLoadingOccurrences(false);
    }
  }, [accessToken, cameraId, workspaceId]);

  useEffect(() => {
    void loadOccurrences();
  }, [loadOccurrences]);

  async function openOccurrenceClip(event: FallEventResponse) {
    if (!event.has_clip || loadingClipId) return;

    setLoadingClipId(event.id);
    setClipError('');
    try {
      const [me, clip] = await Promise.all([
        getMe(accessToken),
        getFallEventClip(accessToken, event.id),
      ]);
      const decryptedClip = await decryptFallClip(clip.encrypted_clip, clip.key_envelope, me.id);
      if (!decryptedClip || !FileSystem.cacheDirectory) {
        throw new Error('Trecho indisponível');
      }

      const nextClipUri = `${FileSystem.cacheDirectory}vard-fall-${event.id}.mp4`;
      await FileSystem.writeAsStringAsync(nextClipUri, bytesToBase64(decryptedClip), {
        encoding: FileSystem.EncodingType.Base64,
      });
      await clipPlayer.replaceAsync(nextClipUri);
      clipPlayer.play();
      setClipUri(nextClipUri);
      setIsClipVisible(true);
    } catch (error) {
      setClipError(
        error instanceof ApiRequestError && error.status === 401
          ? 'Sua sessão expirou. Entre novamente para abrir o trecho.'
          : 'Não foi possível abrir o trecho desta ocorrência.'
      );
    } finally {
      setLoadingClipId(null);
    }
  }

  async function closeOccurrenceClip() {
    clipPlayer.pause();
    setIsClipVisible(false);
    if (clipUri) {
      await FileSystem.deleteAsync(clipUri, { idempotent: true });
      setClipUri(null);
    }
  }

  const handleRefreshOccurrences = useCallback(async () => {
    setIsRefreshingOccurrences(true);
    try {
      await loadOccurrences();
    } finally {
      setIsRefreshingOccurrences(false);
    }
  }, [loadOccurrences]);

  return (
    <LayoutWithNavbar>
      <View style={styles.container}>
        <ScrollView
          contentContainerStyle={styles.content}
          refreshControl={
            <RefreshControl
              colors={['#019BDE']}
              onRefresh={handleRefreshOccurrences}
              refreshing={isRefreshingOccurrences}
              tintColor="#019BDE"
            />
          }
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.headerRow}>
            <Pressable onPress={() => navigation.goBack()} style={styles.backButton}>
              <Feather color="#111827" name="chevron-left" size={20} />
            </Pressable>
            <View style={styles.headerTitleWrap}>
              <Text style={styles.title}>Ocorrências</Text>
              <Text numberOfLines={1} style={styles.occurrencesCameraName}>{cameraName}</Text>
            </View>
          </View>

          {isLoadingOccurrences ? (
            <View style={styles.occurrencesState}>
              <ActivityIndicator color="#019BDE" />
              <Text style={styles.occurrencesStateText}>Carregando ocorrências...</Text>
            </View>
          ) : occurrencesError ? (
            <View style={styles.occurrencesState}>
              <Feather color="#B42318" name="alert-circle" size={28} />
              <Text style={[styles.occurrencesStateText, styles.occurrencesErrorText]}>
                {occurrencesError}
              </Text>
            </View>
          ) : occurrences.length === 0 ? (
            <View style={styles.occurrencesState}>
              <Feather color="#039855" name="check-circle" size={32} />
              <Text style={styles.occurrencesEmptyTitle}>Nenhuma ocorrência</Text>
              <Text style={styles.occurrencesStateText}>
                Esta câmera não possui ocorrências registradas.
              </Text>
            </View>
          ) : (
            <View style={styles.occurrencesList}>
              {occurrences.map((occurrence) => {
                const fallEvent = fallEventsByNotificationId[occurrence.id];
                const canOpenClip = Boolean(fallEvent?.has_clip);
                const isOpeningClip = loadingClipId === fallEvent?.id;

                return (
                  <Pressable
                    accessibilityLabel={
                      canOpenClip ? `Visualizar trecho de ${occurrence.title}` : undefined
                    }
                    accessibilityRole={canOpenClip ? 'button' : undefined}
                    disabled={!canOpenClip || Boolean(loadingClipId)}
                    key={occurrence.id}
                    onPress={() => fallEvent && void openOccurrenceClip(fallEvent)}
                    style={({ pressed }) => [
                      styles.occurrenceCard,
                      pressed && styles.occurrenceCardPressed,
                    ]}
                  >
                    <View style={styles.occurrenceIcon}>
                      <Feather color="#B42318" name="alert-triangle" size={20} />
                    </View>
                    <View style={styles.occurrenceContent}>
                      <Text style={styles.occurrenceTitle}>{occurrence.title}</Text>
                      <Text style={styles.occurrenceBody}>{occurrence.body}</Text>
                      <View style={styles.occurrenceFooter}>
                        <Text style={styles.occurrenceDate}>
                          {formatOccurrenceDate(occurrence.created_at)}
                        </Text>
                        {isOpeningClip ? (
                          <ActivityIndicator color="#019BDE" size="small" />
                        ) : canOpenClip ? (
                          <View style={styles.occurrenceClipAction}>
                            <Feather color="#00326D" name="play-circle" size={16} />
                            <Text style={styles.occurrenceClipActionText}>Ver trecho</Text>
                          </View>
                        ) : (
                          <Text style={styles.occurrenceClipUnavailable}>Sem trecho</Text>
                        )}
                      </View>
                    </View>
                  </Pressable>
                );
              })}
              {clipError ? <Text style={styles.occurrenceClipError}>{clipError}</Text> : null}
            </View>
          )}
        </ScrollView>

        <Modal
          animationType="fade"
          onRequestClose={() => void closeOccurrenceClip()}
          transparent
          visible={isClipVisible}
        >
          <View style={styles.occurrenceClipBackdrop}>
            <View style={styles.occurrenceClipModal}>
              <View style={styles.occurrenceClipHeader}>
                <View>
                  <Text style={styles.occurrenceClipEyebrow}>OCORRÊNCIA</Text>
                  <Text style={styles.occurrenceClipTitle}>Trecho da queda</Text>
                </View>
                <Pressable
                  accessibilityLabel="Fechar vídeo"
                  onPress={() => void closeOccurrenceClip()}
                  style={styles.occurrenceClipClose}
                >
                  <Feather color="#344054" name="x" size={21} />
                </Pressable>
              </View>
              <VideoView
                contentFit="contain"
                nativeControls
                player={clipPlayer}
                style={styles.occurrenceClipVideo}
              />
            </View>
          </View>
        </Modal>
      </View>
    </LayoutWithNavbar>
  );
}

function bytesToBase64(value: Uint8Array) {
  const chunkSize = 0x8000;
  let binary = '';
  for (let index = 0; index < value.length; index += chunkSize) {
    binary += String.fromCharCode(...value.subarray(index, index + chunkSize));
  }
  return btoa(binary);
}

function formatOccurrenceDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString('pt-BR', {
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

function getMemberLabel(member: FamilyMember) {
  return member.contact;
}

function formatMemberRole(role: MemberRole) {
  const labels: Record<MemberRole, string> = {
    admin: 'Administrador',
    caregiver: 'Cuidador',
    member: 'Membro',
    viewer: 'Visualizador',
  };

  return labels[role];
}

function getCameraMetadata(camera: CameraResponse) {
  return camera.metadata ?? camera.metadata_json ?? {};
}

function getCameraLocation(camera: CameraResponse) {
  const metadata = getCameraMetadata(camera);
  const location = firstString(metadata.location, metadata.room, metadata.roomName);
  return location || camera.name || 'Local não definido';
}

function getCameraProtocolValue(camera: CameraResponse): CameraProtocol {
  const metadata = getCameraMetadata(camera);
  const protocol = firstString(metadata.protocol);

  if (
    protocol === 'http-auto' ||
    protocol === 'https-manual' ||
    protocol === 'local-agent-webcam' ||
    protocol === 'local-webview' ||
    protocol === 'rtsp-auto' ||
    protocol === 'rtsp-manual'
  ) {
    return protocol;
  }

  if (camera.connection_type === 'https') {
    return 'https-manual';
  }

  if (camera.connection_type === 'rtsp') {
    return 'rtsp-manual';
  }

  return 'local-webview';
}

function getCameraConnectionLabel(camera: CameraResponse) {
  const protocol = getCameraProtocolValue(camera);
  const labels: Record<CameraProtocol, string> = {
    'http-auto': 'HTTP detectado',
    'https-manual': 'HTTPS manual',
    'local-agent-webcam': 'Webcam deste computador',
    'local-webview': 'Câmera local',
    'rtsp-auto': 'RTSP detectado',
    'rtsp-manual': 'RTSP manual',
  };

  return labels[protocol];
}

function buildRoomCards(cameras: CameraResponse[]) {
  return cameras.map((camera, index) => ({
    id: camera.id,
    camera,
    connectionLabel: getCameraConnectionLabel(camera),
    imageUrl: camera.room_image_url || defaultRoomImageForIndex(index),
    location: getCameraLocation(camera),
    name: camera.name || `Câmera ${index + 1}`,
    updatedAtLabel: camera.updated_at
      ? `Atualizado em ${new Date(camera.updated_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`
      : 'Imagem recebida do backend',
  }));
}

function firstString(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
    }
  }

  return '';
}

function parseCameraConnection(camera: CameraResponse) {
  try {
    const parsed = new URL(camera.stream_url);
    return {
      host: parsed.port ? `${parsed.hostname}:${parsed.port}` : parsed.hostname,
      username: decodeURIComponent(parsed.username),
    };
  } catch {
    return { host: '', username: '' };
  }
}

function defaultRoomImageForIndex(index: number) {
  return `https://picsum.photos/seed/vard-room-${index + 1}/480/300`;
}
