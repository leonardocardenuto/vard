import { Feather, Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { RouteProp, useFocusEffect, useNavigation, useRoute } from '@react-navigation/native';
import { createNativeStackNavigator, NativeStackNavigationProp, NativeStackScreenProps } from '@react-navigation/native-stack';
import { useFonts } from 'expo-font';
import * as ImagePicker from 'expo-image-picker';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { LinearGradient as ExpoLinearGradient } from 'expo-linear-gradient';
import { useCallback, useMemo, useState, type ReactNode } from 'react';
import {
  ActivityIndicator,
  Image,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  Modal,
  RefreshControl,
  ScrollView,
  Text,
  TextInput,
  View,
} from 'react-native';
import Svg, { Defs, LinearGradient, Stop, Text as SvgText } from 'react-native-svg';

import { LayoutWithNavbar } from '../../../components/LayoutWithNavbar';
import {
  ApiRequestError,
  WorkspaceResponse,
  acceptInvite,
  buildDefaultWorkspaceSlug,
  createWorkspace,
  deleteWorkspace,
  listWorkspaces,
  updateWorkspace,
} from '../../../lib/api';
import { AppTabParamList } from '../../../navigation/types';
import { WorkspaceFeedback, WorkspaceFeedbackModal } from '../components/WorkspaceFeedbackModal';
import {
  WORKSPACE_GRADIENT_COLORS,
  WORKSPACE_GRADIENT_LOCATIONS,
  WORKSPACES_FONTS,
  styles,
} from '../styles/workspaces';
import { WorkspaceStackParamList } from '../types/workspace';
import WorkspaceDetailsScreen, {
  WorkspaceCameraLiveViewScreen,
  WorkspaceCameraOccurrencesScreen,
} from './workspace_details';

type WorkspaceTabRoute = RouteProp<AppTabParamList, 'Workspace'>;
type WorkspacesListNavigation = NativeStackNavigationProp<WorkspaceStackParamList, 'WorkspacesList'>;
type WorkspacesListProps = NativeStackScreenProps<WorkspaceStackParamList, 'WorkspacesList'>;
type AddWorkspaceProps = NativeStackScreenProps<WorkspaceStackParamList, 'AddWorkspace'>;
type EditWorkspaceProps = NativeStackScreenProps<WorkspaceStackParamList, 'EditWorkspace'>;

const Stack = createNativeStackNavigator<WorkspaceStackParamList>();
const WORKSPACE_CARD_IMAGES = [
  'https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?auto=format&fit=crop&w=900&q=80',
  'https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?auto=format&fit=crop&w=900&q=80',
  'https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?auto=format&fit=crop&w=900&q=80',
  'https://images.unsplash.com/photo-1600607687920-4e2a09cf159d?auto=format&fit=crop&w=900&q=80',
];

export default function Workspaces() {
  const route = useRoute<WorkspaceTabRoute>();
  const accessToken = route.params?.accessToken ?? '';
  const userEmail = route.params?.userEmail ?? '';
  const userName = route.params?.userName;

  return (
    <Stack.Navigator screenOptions={{ headerShown: false, animation: 'slide_from_right' }}>
      <Stack.Screen
        name="WorkspacesList"
        component={WorkspacesListScreen}
        initialParams={{ accessToken, userEmail, userName }}
      />
      <Stack.Screen name="WorkspaceDetails" component={WorkspaceDetailsScreen} />
      <Stack.Screen name="CameraLiveView" component={WorkspaceCameraLiveViewScreen} />
      <Stack.Screen name="CameraOccurrences" component={WorkspaceCameraOccurrencesScreen} />
      <Stack.Screen
        name="AddWorkspace"
        component={AddWorkspaceScreen}
        initialParams={{ accessToken, userEmail, userName }}
      />
      <Stack.Screen name="EditWorkspace" component={EditWorkspaceScreen} />
    </Stack.Navigator>
  );
}

function WorkspacesListScreen({ route }: WorkspacesListProps) {
  const navigation = useNavigation<WorkspacesListNavigation>();
  const { accessToken, userEmail, userName } = route.params;
  const [workspaces, setWorkspaces] = useState<WorkspaceResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [menuWorkspace, setMenuWorkspace] = useState<WorkspaceResponse | null>(null);
  const [deleteWorkspaceTarget, setDeleteWorkspaceTarget] = useState<WorkspaceResponse | null>(null);
  const [isAcceptInviteOpen, setIsAcceptInviteOpen] = useState(false);
  const [inviteCode, setInviteCode] = useState('');
  const [isAcceptingInvite, setIsAcceptingInvite] = useState(false);
  const [feedback, setFeedback] = useState<WorkspaceFeedback | null>(null);
  const fontsLoaded = useWorkspaceFonts();

  const loadWorkspaces = useCallback(async () => {
    if (!accessToken) {
      setErrorMessage('Sessão inválida. Faça login novamente.');
      setIsLoading(false);
      return;
    }

    try {
      setErrorMessage('');
      setIsLoading(true);
      const workspaceList = await listWorkspaces(accessToken);
      setWorkspaces(uniqueWorkspaces(workspaceList));
    } catch (error) {
      setErrorMessage(
        error instanceof ApiRequestError ? error.message : 'Não foi possível carregar seus espaços.'
      );
    } finally {
      setIsLoading(false);
    }
  }, [accessToken]);

  useFocusEffect( 
    useCallback(() => {
      void loadWorkspaces();
    }, [loadWorkspaces])
  );

  function openWorkspaceMenu(workspace: WorkspaceResponse) {
    setMenuWorkspace(workspace);
  }

  function closeWorkspaceMenu() {
    setMenuWorkspace(null);
  }

  function handleEditWorkspace() {
    if (!menuWorkspace) {
      return;
    }

    const targetWorkspace = menuWorkspace;
    closeWorkspaceMenu();
    navigation.navigate('EditWorkspace', {
      accessToken,
      userEmail,
      userName,
      workspace: targetWorkspace,
    });
  }

  function handleDeleteWorkspace() {
    if (!menuWorkspace) {
      return;
    }

    closeWorkspaceMenu();
    setDeleteWorkspaceTarget(menuWorkspace);
  }

  function closeDeleteWorkspaceSheet() {
    setDeleteWorkspaceTarget(null);
  }

  function confirmDeleteWorkspace() {
    if (!deleteWorkspaceTarget) {
      return;
    }

    const workspaceName = deleteWorkspaceTarget.name;
    void (async () => {
      try {
        await deleteWorkspace(accessToken, deleteWorkspaceTarget.id);
        setWorkspaces((current) => current.filter((workspace) => workspace.id !== deleteWorkspaceTarget.id));
        setFeedback({
          title: 'Espaço excluído',
          message: `${workspaceName} foi excluído com sucesso.`,
          tone: 'success',
        });
      } catch (error) {
        setFeedback({
          title: 'Não foi possível excluir',
          message: error instanceof ApiRequestError ? error.message : 'Tente novamente em instantes.',
          tone: 'error',
        });
      } finally {
        closeDeleteWorkspaceSheet();
      }
    })();
  }

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      await loadWorkspaces();
    } finally {
      setIsRefreshing(false);
    }
  }, [loadWorkspaces]);

  async function handleAcceptInvite() {
    const trimmedCode = inviteCode.trim();
    if (!trimmedCode) {
      setFeedback({
        title: 'Informe o código',
        message: 'Cole o código recebido para aceitar o convite.',
        tone: 'warning',
      });
      return;
    }

    setIsAcceptingInvite(true);
    try {
      await acceptInvite(accessToken, trimmedCode);
      setIsAcceptInviteOpen(false);
      setInviteCode('');
      await loadWorkspaces();
      setFeedback({
        title: 'Convite aceito!',
        message: 'O novo espaço já está disponível para você.',
        tone: 'success',
      });
    } catch (error) {
      setFeedback({
        title: 'Não foi possível aceitar',
        message: error instanceof ApiRequestError ? error.message : 'Confira o código e tente novamente.',
        tone: 'error',
      });
    } finally {
      setIsAcceptingInvite(false);
    }
  }

  if (!fontsLoaded) {
    return null;
  }

  return (
    <LayoutWithNavbar>
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
        <View style={styles.hero}>
          <View>
            <GradientTitle
              height={50}
              text="Espaços"
              width={160}
            />
            <Text style={styles.subtitle}>Escolha o espaço de família</Text>
          </View>

          <View style={styles.heroActions}>
            <Pressable
              accessibilityLabel="Aceitar convite"
              accessibilityRole="button"
              onPress={() => setIsAcceptInviteOpen(true)}
              style={({ pressed }) => [styles.inviteButton, pressed && styles.pressed]}
            >
              <Feather color="#019BDE" name="key" size={21} />
            </Pressable>
            <Pressable
              accessibilityLabel="Adicionar workspace"
              accessibilityRole="button"
              onPress={() =>
                navigation.navigate("AddWorkspace", {
                  accessToken,
                  userEmail,
                  userName,
                })
              }
              style={({ pressed }) => [
                styles.addButton,
                pressed && styles.pressed,
              ]}
            >
              <Feather color="#019BDE" name="plus" size={40} />
            </Pressable>
          </View>
        </View>

        {errorMessage ? (
          <Text style={styles.errorText}>{errorMessage}</Text>
        ) : null}

        {isLoading ? (
          <View style={styles.centerState}>
            <ActivityIndicator color="#019BDE" />
            <Text style={styles.centerStateText}>Carregando workspaces...</Text>
          </View>
        ) : workspaces.length === 0 ? (
          <View style={styles.emptyCard}>
            <MaterialCommunityIcons
              color="#019BDE"
              name="home-plus-outline"
              size={34}
            />
            <Text style={styles.emptyTitle}>Nenhum workspace cadastrado</Text>
            <Text style={styles.emptyText}>
              Toque no + para criar o primeiro espaço monitorado.
            </Text>
          </View>
        ) : (
          workspaces.map((workspace, index) => (
              <Pressable
                accessibilityRole="button"
                key={workspace.id}
                onPress={() => {
                  if (menuWorkspace?.id === workspace.id) {
                    setMenuWorkspace(null);
                    return;
                  }

                  navigation.navigate("WorkspaceDetails", {
                    accessToken,
                    workspace,
                  });
                }}
                style={({ pressed }) => [
                  styles.workspaceCard,
                  pressed && styles.pressed,
                ]}
              >
                <View style={styles.workspaceImageWrap}>
                  <Image
                    source={{ uri: workspace.image_url || imageForWorkspace(index) }}
                    style={styles.workspaceImage}
                  />
                  <Pressable
                    accessibilityRole="button"
                    accessibilityLabel={`Opções de ${workspace.name}`}
                    onPress={() =>
                      setMenuWorkspace((current) => (current?.id === workspace.id ? null : workspace))
                    }
                    style={styles.workspaceMenuButton}
                  >
                    <Ionicons
                      color="#000000"
                      name="ellipsis-vertical"
                      size={18}
                    />
                  </Pressable>

                </View>
                <View style={styles.workspaceCardFooter}>
                  <Text numberOfLines={1} style={styles.workspaceName}>
                    {workspace.name}
                  </Text>
                  <Feather color="#000000" name="chevron-right" size={22} />
                </View>
              </Pressable>
          ))
        )}
      </ScrollView>

      <Modal
        animationType="fade"
        transparent
        visible={isAcceptInviteOpen}
        onRequestClose={() => !isAcceptingInvite && setIsAcceptInviteOpen(false)}
      >
        <Pressable
          onPress={() => !isAcceptingInvite && setIsAcceptInviteOpen(false)}
          style={styles.workspaceActionsOverlay}
        >
          <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
            <Pressable onPress={() => undefined} style={styles.workspaceActionsCard}>
              <View style={styles.workspaceActionsHandle} />
              <Text style={styles.workspaceActionsTitle}>Aceitar convite</Text>
              <Text style={styles.workspaceActionsSubtitle}>
                Cole o código que você recebeu para entrar no espaço.
              </Text>
              <TextInput
                autoCapitalize="characters"
                autoCorrect={false}
                editable={!isAcceptingInvite}
                onChangeText={setInviteCode}
                placeholder="Código do convite"
                placeholderTextColor="#98A2B3"
                style={styles.inviteCodeInput}
                testID="workspace-accept-invite-code"
                value={inviteCode}
              />
              <Pressable
                accessibilityLabel="Confirmar aceite do convite"
                accessibilityRole="button"
                disabled={isAcceptingInvite}
                onPress={() => void handleAcceptInvite()}
                style={[styles.acceptInviteButton, isAcceptingInvite && styles.acceptInviteButtonDisabled]}
              >
                {isAcceptingInvite ? <ActivityIndicator color="#FFFFFF" /> : null}
                <Text style={styles.acceptInviteButtonText}>
                  {isAcceptingInvite ? 'Aceitando...' : 'Aceitar convite'}
                </Text>
              </Pressable>
              <Pressable
                disabled={isAcceptingInvite}
                onPress={() => setIsAcceptInviteOpen(false)}
                style={styles.workspaceActionsCancel}
              >
                <Text style={styles.workspaceActionsCancelText}>Cancelar</Text>
              </Pressable>
            </Pressable>
          </KeyboardAvoidingView>
        </Pressable>
      </Modal>

      <Modal
        animationType="fade"
        transparent
        visible={menuWorkspace !== null}
        onRequestClose={closeWorkspaceMenu}
      >
        <Pressable onPress={closeWorkspaceMenu} style={styles.workspaceActionsOverlay}>
          <Pressable onPress={() => undefined} style={styles.workspaceActionsCard}>
            <View style={styles.workspaceActionsHandle} />
            <Text style={styles.workspaceActionsTitle}>Ações do espaço</Text>
            <Text numberOfLines={1} style={styles.workspaceActionsSubtitle}>
              {menuWorkspace?.name}
            </Text>

            <Pressable
              onPress={handleEditWorkspace}
              style={({ pressed }) => [styles.workspaceActionRow, pressed && styles.pressed]}
            >
              <View style={styles.workspaceActionIcon}>
                <Feather color="#00326D" name="edit-3" size={20} />
              </View>
              <View style={styles.workspaceActionCopy}>
                <Text style={styles.workspaceActionTitle}>Editar espaço</Text>
                <Text style={styles.workspaceActionDescription}>Alterar nome e imagem</Text>
              </View>
              <Feather color="#98A2B3" name="chevron-right" size={20} />
            </Pressable>

            <Pressable
              onPress={handleDeleteWorkspace}
              style={({ pressed }) => [
                styles.workspaceActionRow,
                styles.workspaceActionDangerRow,
                pressed && styles.pressed,
              ]}
            >
              <View style={[styles.workspaceActionIcon, styles.workspaceActionDangerIcon]}>
                <Feather color="#B42318" name="trash-2" size={20} />
              </View>
              <View style={styles.workspaceActionCopy}>
                <Text style={[styles.workspaceActionTitle, styles.workspaceActionDangerTitle]}>
                  Excluir espaço
                </Text>
                <Text style={styles.workspaceActionDescription}>Remover este espaço e suas configurações</Text>
              </View>
              <Feather color="#D92D20" name="chevron-right" size={20} />
            </Pressable>

            <Pressable onPress={closeWorkspaceMenu} style={styles.workspaceActionsCancel}>
              <Text style={styles.workspaceActionsCancelText}>Cancelar</Text>
            </Pressable>
          </Pressable>
        </Pressable>
      </Modal>

      <Modal
        animationType="fade"
        transparent
        visible={deleteWorkspaceTarget !== null}
        onRequestClose={closeDeleteWorkspaceSheet}
      >
        <Pressable onPress={closeDeleteWorkspaceSheet} style={styles.deleteSheetOverlay}>
          <Pressable onPress={() => undefined} style={styles.deleteSheetCard}>
            <View style={styles.deleteSheetHandle} />
            <View style={styles.deleteSheetWarningIcon}>
              <Feather color="#B42318" name="trash-2" size={24} />
            </View>
            <Text style={styles.deleteSheetTitle}>Confirmar exclusão</Text>
            <Text style={styles.deleteSheetDescription}>
              Você tem certeza que deseja excluir este espaço?
            </Text>

            <Pressable onPress={confirmDeleteWorkspace} style={styles.deleteSheetConfirmButton}>
              <Text style={styles.deleteSheetConfirmText}>Excluir espaço</Text>
            </Pressable>

            <Pressable onPress={closeDeleteWorkspaceSheet} style={styles.deleteSheetCancelButton}>
              <Text style={styles.deleteSheetCancelText}>Cancelar</Text>
            </Pressable>
          </Pressable>
        </Pressable>
      </Modal>

      <WorkspaceFeedbackModal feedback={feedback} onClose={() => setFeedback(null)} />

    </LayoutWithNavbar>
  );
}

function AddWorkspaceScreen({ navigation, route }: AddWorkspaceProps) {
  const { accessToken, userEmail, userName } = route.params;
  const [name, setName] = useState('');
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [isPickingImage, setIsPickingImage] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const fontsLoaded = useWorkspaceFonts();

  const slug = useMemo(() => buildDefaultWorkspaceSlug(name || userEmail || 'vard'), [name, userEmail]);

  async function handleSave() {
    if (isSaving) {
      return;
    }

    const trimmedName = name.trim();

    if (!trimmedName) {
      setErrorMessage('Informe o nome do workspace.');
      return;
    }

    setIsSaving(true);
    setErrorMessage('');

    try {
      const workspace = await createWorkspace(accessToken, {
        name: trimmedName,
        slug,
        timezone: 'America/Sao_Paulo',
        image_url: avatarUrl,
      });
      navigation.replace('WorkspaceDetails', { accessToken, workspace });
    } catch (error) {
      setErrorMessage(
        error instanceof ApiRequestError ? error.message : 'Não foi possível criar o workspace.'
      );
    } finally {
      setIsSaving(false);
    }
  }

  if (!fontsLoaded) {
    return null;
  }

  return (
    <WorkspaceFormLayout
      buttonLabel={isSaving ? 'Criando...' : 'Criar workspace'}
      onBackPress={() => navigation.goBack()}
      onSubmit={handleSave}
      submitDisabled={isSaving || isPickingImage}
      subtitle="Crie um espaço para organizar câmeras, alertas e cuidadores."
      title="Novo espaço"
      errorMessage={errorMessage}
    >
      <WorkspaceAvatarButton
        avatarUrl={avatarUrl}
        disabled={isSaving || isPickingImage}
        isPicking={isPickingImage}
        onRemove={() => setAvatarUrl(null)}
        onPress={() => void pickWorkspaceAvatar(setAvatarUrl, setErrorMessage, setIsPickingImage)}
      />

      <View style={styles.formCard}>
        <Text style={styles.inputLabel}>Nome do espaço</Text>
        <TextInput
          accessibilityLabel="Nome do espaço"
          autoCapitalize="words"
          autoCorrect={false}
          editable={!isSaving}
          maxLength={200}
          testID="workspace-name"
          onChangeText={setName}
          onSubmitEditing={handleSave}
          placeholder={userName ? `Ex.: Casa de ${userName}` : 'Ex.: Casa da família'}
          placeholderTextColor="#98A2B3"
          returnKeyType="done"
          style={styles.input}
          value={name}
        />
      </View>
    </WorkspaceFormLayout>
  );
}

function EditWorkspaceScreen({ navigation, route }: EditWorkspaceProps) {
  const { accessToken, userEmail, userName, workspace } = route.params;
  const [name, setName] = useState(workspace.name);
  const [avatarUrl, setAvatarUrl] = useState<string | null>(workspace.image_url ?? null);
  const [isPickingImage, setIsPickingImage] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const fontsLoaded = useWorkspaceFonts();

  const slug = useMemo(() => buildDefaultWorkspaceSlug(name || userEmail || 'vard'), [name, userEmail]);

  async function handleSave() {
    if (isSaving) {
      return;
    }

    const trimmedName = name.trim();

    if (!trimmedName) {
      setErrorMessage('Informe o nome do workspace.');
      return;
    }

    setIsSaving(true);
    setErrorMessage('');

    try {
      const updatedWorkspace = await updateWorkspace(accessToken, workspace.id, {
        name: trimmedName,
        timezone: workspace.timezone || 'America/Sao_Paulo',
        image_url: avatarUrl,
      });
      navigation.replace('WorkspaceDetails', { accessToken, workspace: updatedWorkspace });
    } catch (error) {
      setErrorMessage(
        error instanceof ApiRequestError ? error.message : 'Não foi possível atualizar o workspace.'
      );
    } finally {
      setIsSaving(false);
    }
  }

  if (!fontsLoaded) {
    return null;
  }

  return (
    <WorkspaceFormLayout
      buttonLabel={isSaving ? 'Salvando...' : 'Salvar alterações'}
      onBackPress={() => navigation.goBack()}
      onSubmit={handleSave}
      submitDisabled={isSaving || isPickingImage}
      subtitle="Atualize o nome e a foto do seu espaço."
      title="Editar espaço"
      errorMessage={errorMessage}
    >

      <WorkspaceAvatarButton
        avatarUrl={avatarUrl}
        disabled={isSaving || isPickingImage}
        isPicking={isPickingImage}
        onRemove={() => setAvatarUrl(null)}
        onPress={() => void pickWorkspaceAvatar(setAvatarUrl, setErrorMessage, setIsPickingImage)}
      />
      <View style={styles.formCard}>
        <Text style={styles.inputLabel}>Nome do espaço</Text>
        <TextInput
          accessibilityLabel="Nome do espaço"
          autoCapitalize="words"
          autoCorrect={false}
          editable={!isSaving}
          maxLength={200}
          testID="workspace-name"
          onChangeText={setName}
          onSubmitEditing={handleSave}
          placeholder="Ex.: Casa da Família"
          placeholderTextColor="#98A2B3"
          returnKeyType="done"
          style={styles.input}
          value={name}
        />
      </View>
    </WorkspaceFormLayout>
  );
}

function WorkspaceAvatarButton({ avatarUrl, onPress, onRemove, disabled, isPicking }: {
  avatarUrl: string | null;
  onPress: () => void;
  onRemove: () => void;
  disabled: boolean;
  isPicking: boolean;
}) {
  return (
    <View style={styles.photoSection}>
      <Text style={styles.inputLabel}>Foto de capa</Text>
      <Pressable testID="workspace-photo" accessibilityRole="button"
        accessibilityLabel={avatarUrl ? 'Trocar foto do espaço' : 'Selecionar foto do espaço'}
        accessibilityState={{ disabled, busy: isPicking }} disabled={disabled} onPress={onPress}
        style={({ pressed }) => [styles.photoPreview, (pressed || disabled) && styles.pressed]}>
        {avatarUrl ? <Image source={{ uri: avatarUrl }} resizeMode="cover" style={styles.avatarImage} /> : (
          <View style={styles.photoPlaceholder}>
            <View style={styles.photoIcon}><Feather color="#019BDE" name="image" size={24} /></View>
            <Text style={styles.photoTitle}>Escolher foto</Text>
            <Text style={styles.avatarHintText}>Selecione uma imagem da galeria</Text>
          </View>
        )}
        {isPicking ? <View style={styles.photoLoading}><ActivityIndicator color="#019BDE" /></View> : null}
      </Pressable>
      {avatarUrl ? <View style={styles.photoActions}>
        <Pressable accessibilityRole="button" disabled={disabled} onPress={onPress} style={styles.photoAction}>
          <Feather name="image" size={18} color="#019BDE" /><Text style={styles.photoActionText}>Trocar foto</Text>
        </Pressable>
        <Pressable testID="workspace-photo-remove" accessibilityRole="button" disabled={disabled} onPress={onRemove} style={styles.photoAction}>
          <Feather name="trash-2" size={18} color="#B42318" /><Text style={styles.photoRemoveText}>Remover</Text>
        </Pressable>
      </View> : null}
    </View>
  );
}

async function pickWorkspaceAvatar(
  setAvatarUrl: (value: string | null) => void,
  setErrorMessage: (value: string) => void,
  setIsPicking: (value: boolean) => void,
) {
  setIsPicking(true);
  setErrorMessage('');
  try {
    const result = await ImagePicker.launchImageLibraryAsync({
      allowsEditing: true,
      aspect: [16, 9],
      base64: true,
      mediaTypes: ['images'],
      quality: 0.72,
    });
    if (result.canceled || !result.assets[0]) return;
    const asset = result.assets[0];
    if (!asset.base64) throw new Error('Não foi possível ler a foto. Escolha outra imagem.');
    // Native picker returns JPEG; web preserves the selected file format.
    const mimeType = Platform.OS === 'web' ? (asset.mimeType || 'image/jpeg') : 'image/jpeg';
    const image = `data:${mimeType};base64,${asset.base64}`;
    if (image.length > 7_000_000) throw new Error('A foto é muito grande. Escolha uma imagem menor que 5 MB.');
    setAvatarUrl(image);
  } catch (error) {
    setErrorMessage(error instanceof Error ? error.message : 'Não foi possível abrir a galeria. Tente novamente.');
  } finally {
    setIsPicking(false);
  }
}

function WorkspaceFormLayout({
  buttonLabel, children, errorMessage, onBackPress, onSubmit, submitDisabled, subtitle, title,
}: {
  buttonLabel: string;
  children: React.ReactNode;
  errorMessage: string;
  onBackPress: () => void;
  onSubmit: () => void;
  submitDisabled: boolean;
  subtitle: string;
  title: string;
}) {
  const insets = useSafeAreaInsets();
  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={72 + insets.top}
      style={[styles.formScreen, { paddingBottom: 64 + Math.max(insets.bottom, 10) }]}
    >
      <ScrollView contentContainerStyle={styles.formScreenContent}
        keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
        <View style={styles.formHeader}>
          <Pressable accessibilityRole="button" accessibilityLabel="Voltar" onPress={onBackPress}
            style={({ pressed }) => [styles.backButton, pressed && styles.pressed]}>
            <Feather color="#344054" name="arrow-left" size={21} />
          </Pressable>
          <Text accessibilityRole="header" style={styles.formTitle}>{title}</Text>
          <View style={styles.headerBalance} />
        </View>
        <Text style={styles.formDescription}>{subtitle}</Text>
        <View style={styles.formBody}>{children}</View>
        {errorMessage ? <Text accessibilityLiveRegion="polite" style={styles.errorText}>{errorMessage}</Text> : null}
      </ScrollView>
      <View style={styles.formFooter}>
        <View style={styles.footerContent}>
          <Pressable accessibilityRole="button" accessibilityState={{ disabled: submitDisabled }}
            testID="workspace-save" disabled={submitDisabled} onPress={onSubmit}
            style={({ pressed }) => [styles.primaryButton, (pressed || submitDisabled) && styles.pressed]}>
            <ExpoLinearGradient
              colors={WORKSPACE_GRADIENT_COLORS}
              locations={WORKSPACE_GRADIENT_LOCATIONS}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 1 }}
              style={styles.primaryButtonGradient}
            >
              <Text style={styles.primaryButtonText}>{buttonLabel}</Text>
            </ExpoLinearGradient>
          </Pressable>
          <Pressable accessibilityRole="button" disabled={submitDisabled} onPress={onBackPress}
            style={({ pressed }) => [styles.cancelButton, pressed && styles.pressed]}>
            <Text style={styles.cancelButtonText}>Cancelar</Text>
          </Pressable>
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}

function GradientTitle({ text }: { height?: number; text: string; width?: number }) {
  return (
    <Svg height={38} style={styles.titleSvg} viewBox="0 0 210 38" width={210}>
      <Defs>
        <LinearGradient id="workspaceTitleGradient" x1="0" x2="1" y1="0" y2="0">
          <Stop offset="8%" stopColor={WORKSPACE_GRADIENT_COLORS[0]} />
          <Stop offset="48%" stopColor={WORKSPACE_GRADIENT_COLORS[1]} />
          <Stop offset="100%" stopColor={WORKSPACE_GRADIENT_COLORS[2]} />
        </LinearGradient>
      </Defs>
      <SvgText
        fill="url(#workspaceTitleGradient)"
        fontFamily={WORKSPACES_FONTS.semiBold}
        fontSize={40}
        fontWeight="900"
        x={0}
        y={31}
      >
        {text}
      </SvgText>
    </Svg>
  );
}

function imageForWorkspace(index: number) {
  return WORKSPACE_CARD_IMAGES[index % WORKSPACE_CARD_IMAGES.length];
}

function uniqueWorkspaces(workspaces: WorkspaceResponse[]) {
  return workspaces.filter((workspace, index, allWorkspaces) =>
    allWorkspaces.findIndex((current) => current.id === workspace.id) === index
  );
}

function useWorkspaceFonts() {
  const [fontsLoaded] = useFonts({
    [WORKSPACES_FONTS.regular]: require('../../../../assets/fonts/Poppins-Regular.ttf'),
    [WORKSPACES_FONTS.medium]: require('../../../../assets/fonts/Poppins-Medium.ttf'),
    [WORKSPACES_FONTS.bold]: require('../../../../assets/fonts/Poppins-Bold.ttf'),
    [WORKSPACES_FONTS.extraBold]: require('../../../../assets/fonts/Poppins-ExtraBold.ttf'),
  });

  return fontsLoaded;
}
