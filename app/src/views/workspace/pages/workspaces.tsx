import { Feather, Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { RouteProp, useFocusEffect, useNavigation, useRoute } from '@react-navigation/native';
import { createNativeStackNavigator, NativeStackNavigationProp, NativeStackScreenProps } from '@react-navigation/native-stack';
import { useFonts } from 'expo-font';
import * as ImagePicker from 'expo-image-picker';
import { LinearGradient as ExpoLinearGradient } from 'expo-linear-gradient';
import { useCallback, useMemo, useState, type ReactNode } from 'react';
import {
  ActivityIndicator,
  Alert,
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
  buildDefaultWorkspaceSlug,
  createWorkspace,
  deleteWorkspace,
  listWorkspaces,
  updateWorkspace,
} from '../../../lib/api';
import { AppTabParamList } from '../../../navigation/types';
import {
  WORKSPACE_GRADIENT_COLORS,
  WORKSPACE_GRADIENT_LOCATIONS,
  WORKSPACES_FONTS,
  styles,
} from '../styles/workspaces';
import { WorkspaceStackParamList } from '../types/workspace';
import WorkspaceDetailsScreen, { WorkspaceCameraLiveViewScreen } from './workspace_details';

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
  const fontsLoaded = useWorkspaceFonts();

  const loadWorkspaces = useCallback(async () => {
    if (!accessToken) {
      setErrorMessage('Sessao invalida. Faca login novamente.');
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
        error instanceof ApiRequestError ? error.message : 'Nao foi possivel carregar seus espacos.'
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

    void (async () => {
      try {
        await deleteWorkspace(accessToken, deleteWorkspaceTarget.id);
        setWorkspaces((current) => current.filter((workspace) => workspace.id !== deleteWorkspaceTarget.id));
      } catch (error) {
        Alert.alert(
          'Nao foi possivel excluir',
          error instanceof ApiRequestError ? error.message : 'Tente novamente em instantes.'
        );
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
            <Text style={styles.subtitle}>Escolha o espaco de familia</Text>
          </View>

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
              Toque no + para criar o primeiro espaco monitorado.
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
                    source={{ uri: imageForWorkspace(index) }}
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

                  {menuWorkspace?.id === workspace.id ? (
                    <View style={styles.menuCardInline}>
                      <Text style={styles.menuTitle}>{workspace.name}</Text>
                      <Text style={styles.menuSubtitle}>Escolha uma acao para este espaco.</Text>

                      <Pressable onPress={handleEditWorkspace} style={styles.menuItem}>
                        <Feather color="#475467" name="edit-3" size={16} />
                        <Text style={styles.menuItemText}>Editar</Text>
                      </Pressable>

                      <Pressable onPress={handleDeleteWorkspace} style={styles.menuItem}>
                        <Feather color="#B42318" name="trash-2" size={16} />
                        <Text style={[styles.menuItemText, styles.menuDangerText]}>Excluir</Text>
                      </Pressable>
                    </View>
                  ) : null}
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
        visible={deleteWorkspaceTarget !== null}
        onRequestClose={closeDeleteWorkspaceSheet}
      >
        <Pressable onPress={closeDeleteWorkspaceSheet} style={styles.deleteSheetOverlay}>
          <Pressable onPress={() => undefined} style={styles.deleteSheetCard}>
            <View style={styles.deleteSheetHandle} />
            <Text style={styles.deleteSheetTitle}>Confirmar exclusão</Text>
            <Text style={styles.deleteSheetDescription}>
              Você tem certeza que deseja excluir este espaço?
            </Text>

            <Pressable onPress={confirmDeleteWorkspace} style={styles.deleteSheetConfirmButton}>
              <Text style={styles.deleteSheetConfirmText}>Sim, eu tenho certeza</Text>
            </Pressable>

            <Pressable onPress={closeDeleteWorkspaceSheet} style={styles.deleteSheetCancelButton}>
              <Text style={styles.deleteSheetCancelText}>Cancelar</Text>
            </Pressable>
          </Pressable>
        </Pressable>
      </Modal>

    </LayoutWithNavbar>
  );
}

function AddWorkspaceScreen({ navigation, route }: AddWorkspaceProps) {
  const { accessToken, userEmail, userName } = route.params;
  const [name, setName] = useState(userName ? `Casa de ${userName}` : '');
  const [timezone, setTimezone] = useState('America/Sao_Paulo');
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const fontsLoaded = useWorkspaceFonts();

  const slug = useMemo(() => buildDefaultWorkspaceSlug(name || userEmail || 'vard'), [name, userEmail]);

  async function handleSave() {
    if (isSaving) {
      return;
    }

    const trimmedName = name.trim();
    const trimmedTimezone = timezone.trim() || 'America/Sao_Paulo';

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
        timezone: trimmedTimezone,
      });
      navigation.replace('WorkspaceDetails', { accessToken, workspace });
    } catch (error) {
      setErrorMessage(
        error instanceof ApiRequestError ? error.message : 'Nao foi possivel criar o workspace.'
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
      submitDisabled={isSaving}
      subtitle="Crie um espaço para organizar cameras, alertas e cuidadores."
      title="Novo Espaço"
      errorMessage={errorMessage}
    >
      <WorkspaceAvatarButton
        avatarUrl={avatarUrl}
        onPress={() => void pickWorkspaceAvatar(setAvatarUrl, setErrorMessage)}
      />

      <View style={styles.formCard}>
        <Text style={styles.inputLabel}>Nome do Workspace</Text>
        <TextInput
          onChangeText={setName}
          placeholder="Ex.: Casa da Familia"
          placeholderTextColor="#98A2B3"
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
  const [timezone, setTimezone] = useState(workspace.timezone);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const fontsLoaded = useWorkspaceFonts();

  const slug = useMemo(() => buildDefaultWorkspaceSlug(name || userEmail || 'vard'), [name, userEmail]);

  async function handleSave() {
    if (isSaving) {
      return;
    }

    const trimmedName = name.trim();
    const trimmedTimezone = timezone.trim() || 'America/Sao_Paulo';

    if (!trimmedName) {
      setErrorMessage('Informe o nome do workspace.');
      return;
    }

    setIsSaving(true);
    setErrorMessage('');

    try {
      const updatedWorkspace = await updateWorkspace(accessToken, workspace.id, {
        name: trimmedName,
        timezone: trimmedTimezone,
      });
      navigation.replace('WorkspaceDetails', { accessToken, workspace: updatedWorkspace });
    } catch (error) {
      setErrorMessage(
        error instanceof ApiRequestError ? error.message : 'Nao foi possivel atualizar o workspace.'
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
      submitDisabled={isSaving}
      subtitle={`Edite o espaço "${workspace.name}" antes de salvar no backend.`}
      title="Editar Espaço"
      errorMessage={errorMessage}
    >

      <View style={styles.formCard}>
        <Text style={styles.inputLabel}>Nome do Workspace</Text>
        <TextInput
          onChangeText={setName}
          placeholder="Ex.: Casa da Familia"
          placeholderTextColor="#98A2B3"
          style={styles.input}
          value={name}
        />
      </View>
    </WorkspaceFormLayout>
  );
}

function WorkspaceAvatarButton({
  avatarUrl,
  onPress,
}: {
  avatarUrl: string | null;
  onPress: () => void;
}) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={styles.avatarWrap}>
      <View style={styles.avatarCircle}>
        {avatarUrl ? (
          <Image source={{ uri: avatarUrl }} style={styles.avatarImage} />
        ) : (
          <Feather color="#A3AAB5" name="camera" size={40} />
        )}
        <View style={styles.avatarPlusBubble}>
          <Text style={styles.avatarPlusBubbleText}>+</Text>
        </View>
      </View>
      <Text style={styles.avatarHintText}>Selecionar foto</Text>
    </Pressable>
  );
}

async function pickWorkspaceAvatar(
  setAvatarUrl: (value: string | null) => void,
  setErrorMessage: (value: string) => void
) {
  const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();

  if (!permission.granted) {
    Alert.alert('Permissao necessaria', 'Permita acesso às suas fotos para escolher a imagem do workspace.');
    return;
  }

  const result = await ImagePicker.launchImageLibraryAsync({
    allowsEditing: true,
    aspect: [1, 1],
    base64: true,
    mediaTypes: ImagePicker.MediaTypeOptions.Images,
    quality: 0.72,
  });

  if (result.canceled || !result.assets[0]) {
    return;
  }

  const asset = result.assets[0];
  const workspaceAvatarUrl = asset.base64
    ? `data:${asset.mimeType ?? 'image/jpeg'};base64,${asset.base64}`
    : asset.uri;

  setErrorMessage('');
  setAvatarUrl(workspaceAvatarUrl);
}

function WorkspaceFormLayout({
  buttonLabel,
  children,
  errorMessage,
  onBackPress,
  onSubmit,
  submitDisabled,
  subtitle,
  title,
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
  return (
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={styles.flex}>
      <ScrollView contentContainerStyle={styles.formScreenContent} keyboardShouldPersistTaps="handled">
        <View style={styles.formHeader}>
          <Pressable onPress={onBackPress} style={styles.backButton}>
            <Feather color="#111827" name="chevron-left" size={20} />
          </Pressable>
          <View style={styles.formHeaderText}>
            <Text style={styles.titleSmall}>{title}</Text>
            <Text style={styles.subtitle}>{subtitle}</Text>
          </View>
        </View>

        {children}

        {errorMessage ? <Text style={styles.errorText}>{errorMessage}</Text> : null}

        <Pressable
          disabled={submitDisabled}
          onPress={onSubmit}
          style={({ pressed }) => [styles.primaryButton, (pressed || submitDisabled) && styles.pressed]}
        >
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
      </ScrollView>
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
