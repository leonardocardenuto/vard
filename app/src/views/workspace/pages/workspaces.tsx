import { Feather, Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { RouteProp, useFocusEffect, useNavigation, useRoute } from '@react-navigation/native';
import { createNativeStackNavigator, NativeStackNavigationProp, NativeStackScreenProps } from '@react-navigation/native-stack';
import { useFonts } from 'expo-font';
import { LinearGradient as ExpoLinearGradient } from 'expo-linear-gradient';
import { useCallback, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  KeyboardAvoidingView,
  Platform,
  Pressable,
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
  listWorkspaces,
} from '../../../lib/api';
import { AppTabParamList } from '../../../navigation/types';
import {
  WORKSPACE_GRADIENT_COLORS,
  WORKSPACE_GRADIENT_LOCATIONS,
  WORKSPACES_FONTS,
  styles,
} from '../workspaces';
import { WorkspaceStackParamList } from '../types/workspace';
import WorkspaceDetailsScreen from './workspace_details';

type WorkspaceTabRoute = RouteProp<AppTabParamList, 'Workspace'>;
type WorkspacesListNavigation = NativeStackNavigationProp<WorkspaceStackParamList, 'WorkspacesList'>;
type WorkspacesListProps = NativeStackScreenProps<WorkspaceStackParamList, 'WorkspacesList'>;
type AddWorkspaceProps = NativeStackScreenProps<WorkspaceStackParamList, 'AddWorkspace'>;

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
      <Stack.Screen
        name="AddWorkspace"
        component={AddWorkspaceScreen}
        initialParams={{ accessToken, userEmail, userName }}
      />
    </Stack.Navigator>
  );
}

function WorkspacesListScreen({ route }: WorkspacesListProps) {
  const navigation = useNavigation<WorkspacesListNavigation>();
  const { accessToken, userEmail, userName } = route.params;
  const [workspaces, setWorkspaces] = useState<WorkspaceResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState('');
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
      setWorkspaces(await listWorkspaces(accessToken));
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

  if (!fontsLoaded) {
    return null;
  }

  return (
    <LayoutWithNavbar>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.hero}>
          <View>
            <GradientTitle
                  height={42}
                  text="Espaços"
                  width={160}
                />
            <Text style={styles.subtitle}>Escolha o espaco de familia</Text>
          </View>

          <Pressable
            accessibilityLabel="Adicionar workspace"
            accessibilityRole="button"
            onPress={() => navigation.navigate('AddWorkspace', { accessToken, userEmail, userName })}
            style={({ pressed }) => [styles.addButton, pressed && styles.pressed]}
          >
            <ExpoLinearGradient
              colors={WORKSPACE_GRADIENT_COLORS}
              locations={WORKSPACE_GRADIENT_LOCATIONS}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 1 }}
              style={styles.addButtonGradient}
            >
              <View style={styles.addButtonInner}>
                <Feather color="#019BDE" name="plus" size={26} />
              </View>
            </ExpoLinearGradient>
          </Pressable>
        </View>

        {errorMessage ? <Text style={styles.errorText}>{errorMessage}</Text> : null}

        {isLoading ? (
          <View style={styles.centerState}>
            <ActivityIndicator color="#019BDE" />
            <Text style={styles.centerStateText}>Carregando workspaces...</Text>
          </View>
        ) : workspaces.length === 0 ? (
          <View style={styles.emptyCard}>
            <MaterialCommunityIcons color="#019BDE" name="home-plus-outline" size={34} />
            <Text style={styles.emptyTitle}>Nenhum workspace cadastrado</Text>
            <Text style={styles.emptyText}>Toque no + para criar o primeiro espaco monitorado.</Text>
          </View>
        ) : (
          workspaces.map((workspace, index) => (
            <ExpoLinearGradient
              colors={WORKSPACE_GRADIENT_COLORS}
              key={workspace.id}
              locations={WORKSPACE_GRADIENT_LOCATIONS}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 1 }}
              style={styles.workspaceCardGradient}
            >
              <Pressable
                accessibilityRole="button"
                onPress={() => navigation.navigate('WorkspaceDetails', { accessToken, workspace })}
                style={({ pressed }) => [styles.workspaceCard, pressed && styles.pressed]}
              >
                <View style={styles.workspaceImageWrap}>
                  <Image source={{ uri: imageForWorkspace(index) }} style={styles.workspaceImage} />
                  <Pressable accessibilityRole="button" style={styles.workspaceMenuButton}>
                    <Ionicons color="#019BDE" name="ellipsis-vertical" size={18} />
                  </Pressable>
                </View>
                <View style={styles.workspaceCardFooter}>
                  <Text numberOfLines={1} style={styles.workspaceName}>{workspace.name}</Text>
                  <Feather color="#101828" name="chevron-right" size={22} />
                </View>
              </Pressable>
            </ExpoLinearGradient>
          ))
        )}
      </ScrollView>
    </LayoutWithNavbar>
  );
}

function AddWorkspaceScreen({ navigation, route }: AddWorkspaceProps) {
  const { accessToken, userEmail, userName } = route.params;
  const [name, setName] = useState(userName ? `Casa de ${userName}` : '');
  const [timezone, setTimezone] = useState('America/Sao_Paulo');
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const fontsLoaded = useWorkspaceFonts();

  const slug = useMemo(() => buildDefaultWorkspaceSlug(name || userEmail || 'vard'), [name, userEmail]);

  async function handleSave() {
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
    <LayoutWithNavbar>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={styles.flex}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <View style={styles.formHeader}>
            <Pressable onPress={() => navigation.goBack()} style={styles.backButton}>
              <Feather color="#111827" name="chevron-left" size={20} />
            </Pressable>
            <View style={styles.formHeaderText}>
              <Text style={styles.titleSmall}>Novo workspace</Text>
              <Text style={styles.subtitle}>Crie um espaco para organizar cameras, alertas e cuidadores.</Text>
            </View>
          </View>

          <View style={styles.formCard}>
            <Text style={styles.inputLabel}>Nome</Text>
            <TextInput
              onChangeText={setName}
              placeholder="Ex.: Casa da Familia"
              placeholderTextColor="#98A2B3"
              style={styles.input}
              value={name}
            />

            <Text style={styles.inputLabel}>Fuso horario</Text>
            <TextInput
              autoCapitalize="none"
              onChangeText={setTimezone}
              placeholder="America/Sao_Paulo"
              placeholderTextColor="#98A2B3"
              style={styles.input}
              value={timezone}
            />

            <View style={styles.slugPreview}>
              <Text style={styles.slugLabel}>Slug</Text>
              <Text numberOfLines={1} style={styles.slugValue}>{slug}</Text>
            </View>
          </View>

          {errorMessage ? <Text style={styles.errorText}>{errorMessage}</Text> : null}

          <Pressable
            disabled={isSaving}
            onPress={handleSave}
            style={({ pressed }) => [styles.primaryButton, (pressed || isSaving) && styles.pressed]}
          >
            <ExpoLinearGradient
              colors={WORKSPACE_GRADIENT_COLORS}
              locations={WORKSPACE_GRADIENT_LOCATIONS}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 1 }}
              style={styles.primaryButtonGradient}
            >
              <Text style={styles.primaryButtonText}>{isSaving ? 'Criando...' : 'Criar workspace'}</Text>
            </ExpoLinearGradient>
          </Pressable>
        </ScrollView>
      </KeyboardAvoidingView>
    </LayoutWithNavbar>
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
        fontFamily={WORKSPACES_FONTS.manrope}
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

function useWorkspaceFonts() {
  const [fontsLoaded] = useFonts({
    [WORKSPACES_FONTS.manrope]: require("../../../../assets/fonts/Manrope.ttf"),
    [WORKSPACES_FONTS.regular]: require('../../../../assets/fonts/Poppins-Regular.ttf'),
    [WORKSPACES_FONTS.medium]: require('../../../../assets/fonts/Poppins-Medium.ttf'),
    [WORKSPACES_FONTS.bold]: require('../../../../assets/fonts/Poppins-Bold.ttf'),
    [WORKSPACES_FONTS.extraBold]: require('../../../../assets/fonts/Poppins-ExtraBold.ttf'),
  });

  return fontsLoaded;
}
