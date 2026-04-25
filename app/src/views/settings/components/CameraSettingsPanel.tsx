import { useEffect, useState } from 'react';
import { useVideoPlayer, VideoView } from 'expo-video';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import {
  ApiRequestError,
  buildDefaultWorkspaceSlug,
  buildIntelbrasIm4RtspUrl,
  CameraResponse,
  createCamera,
  createWorkspace,
  listCameras,
  listWorkspaces,
  startCameraHlsStream,
  WorkspaceResponse,
} from '../../../lib/api';

type CameraSettingsPanelProps = {
  accessToken: string;
  userEmail: string;
  userName: string;
};

type CameraFormState = {
  accessKey: string;
  host: string;
  name: string;
};

const initialFormState: CameraFormState = {
  accessKey: '',
  host: '',
  name: '',
};

function getCameraHost(camera: CameraResponse) {
  const host = camera.metadata.host;
  return typeof host === 'string' && host.trim() ? host : 'host não informado';
}

export function CameraSettingsPanel({
  accessToken,
  userEmail,
  userName,
}: CameraSettingsPanelProps) {
  const player = useVideoPlayer(null);

  const [workspace, setWorkspace] = useState<WorkspaceResponse | null>(null);
  const [cameras, setCameras] = useState<CameraResponse[]>([]);
  const [form, setForm] = useState<CameraFormState>(initialFormState);
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isStartingStreamId, setIsStartingStreamId] = useState<string | null>(null);
  const [selectedCameraId, setSelectedCameraId] = useState<string | null>(null);
  const [streamUrl, setStreamUrl] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    async function syncPlayerSource() {
      if (!streamUrl) {
        player.pause();
        return;
      }

      try {
        await player.replaceAsync(streamUrl);
        player.play();
      } catch {
        setErrorMessage('Não foi possível carregar o vídeo ao vivo.');
      }
    }

    void syncPlayerSource();
  }, [player, streamUrl]);

  useEffect(() => {
    let isMounted = true;

    async function bootstrap() {
      if (!accessToken) {
        if (isMounted) {
          setErrorMessage('Sessão inválida. Faça login novamente.');
          setIsBootstrapping(false);
        }
        return;
      }

      try {
        const availableWorkspaces = await listWorkspaces(accessToken);
        const resolvedWorkspace =
          availableWorkspaces[0] ??
          (await createWorkspace(accessToken, {
            name: `Casa de ${userName}`,
            slug: buildDefaultWorkspaceSlug(userEmail || userName),
            timezone: 'America/Sao_Paulo',
          }));
        const workspaceCameras = await listCameras(accessToken, resolvedWorkspace.id);

        if (isMounted) {
          setWorkspace(resolvedWorkspace);
          setCameras(workspaceCameras);
        }
      } catch (error) {
        if (isMounted) {
          setErrorMessage(
            error instanceof ApiRequestError ? error.message : 'Não foi possível carregar os ajustes.'
          );
        }
      } finally {
        if (isMounted) {
          setIsBootstrapping(false);
        }
      }
    }

    void bootstrap();

    return () => {
      isMounted = false;
    };
  }, [accessToken, userEmail, userName]);

  function updateField(field: keyof CameraFormState, value: string) {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function handleCreateCamera() {
    if (!workspace) {
      return;
    }

    const name = form.name.trim();
    const host = form.host.trim();
    const accessKey = form.accessKey.trim();

    if (!name || !host || !accessKey) {
      setErrorMessage('Preencha nome, IP/host e chave de acesso da iM4.');
      return;
    }

    setIsSaving(true);
    setErrorMessage('');

    try {
      const createdCamera = await createCamera(accessToken, {
        workspace_id: workspace.id,
        name,
        connection_type: 'rtsp',
        stream_url: buildIntelbrasIm4RtspUrl(host, accessKey),
        status: 'offline',
        is_active: true,
        metadata: {
          access_key_hint: `${accessKey.slice(0, 2)}***`,
          host,
          model: 'iM4',
          vendor: 'Intelbras',
        },
      });

      setCameras((current) => [createdCamera, ...current]);
      setForm(initialFormState);
    } catch (error) {
      setErrorMessage(
        error instanceof ApiRequestError ? error.message : 'Não foi possível cadastrar a câmera.'
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function handleStartStream(camera: CameraResponse) {
    setIsStartingStreamId(camera.id);
    setErrorMessage('');

    try {
      const response = await startCameraHlsStream(accessToken, camera.id);
      setSelectedCameraId(camera.id);
      setStreamUrl(response.playlist_url);
    } catch (error) {
      setErrorMessage(
        error instanceof ApiRequestError
          ? error.message
          : 'Não foi possível iniciar o stream da câmera.'
      );
    } finally {
      setIsStartingStreamId(null);
    }
  }

  return (
    <ScrollView
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
      showsVerticalScrollIndicator={false}
    >
      <View style={styles.header}>
        <Text style={styles.title}>Ajustes</Text>
        <Text style={styles.subtitle}>
          Cadastre sua Intelbras iM4 pelo IP local e chave de acesso para gerar o stream.
        </Text>
      </View>

      {isBootstrapping ? (
        <View style={styles.centerState}>
          <ActivityIndicator color="#019BDE" />
          <Text style={styles.centerStateText}>Carregando ajustes...</Text>
        </View>
      ) : (
        <>
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>
              {workspace ? workspace.name : 'Seu workspace'}
            </Text>
            <Text style={styles.sectionHint}>
              A Intelbras recomenda RTSP em rede local. O backend precisa alcançar o IP da câmera.
            </Text>
          </View>

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Adicionar câmera</Text>

            <Text style={styles.fieldLabel}>Nome da câmera</Text>
            <TextInput
              onChangeText={(value) => updateField('name', value)}
              placeholder="Ex.: Sala principal"
              placeholderTextColor="#A7AEB7"
              style={styles.input}
              value={form.name}
            />

            <Text style={styles.fieldLabel}>IP ou host da iM4</Text>
            <TextInput
              autoCapitalize="none"
              onChangeText={(value) => updateField('host', value)}
              placeholder="Ex.: 192.168.0.120"
              placeholderTextColor="#A7AEB7"
              style={styles.input}
              value={form.host}
            />

            <Text style={styles.fieldLabel}>Chave de acesso</Text>
            <TextInput
              autoCapitalize="none"
              onChangeText={(value) => updateField('accessKey', value)}
              placeholder="Chave da etiqueta do dispositivo"
              placeholderTextColor="#A7AEB7"
              style={styles.input}
              value={form.accessKey}
            />

            <Pressable
              disabled={isSaving}
              onPress={handleCreateCamera}
              style={[styles.primaryButton, isSaving && styles.buttonDisabled]}
            >
              <Text style={styles.primaryButtonText}>
                {isSaving ? 'Cadastrando...' : 'Cadastrar iM4'}
              </Text>
            </Pressable>

            {errorMessage ? <Text style={styles.errorText}>{errorMessage}</Text> : null}
          </View>

          {streamUrl ? (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Ao vivo</Text>
              <View style={styles.videoCard}>
                <VideoView
                  contentFit="cover"
                  nativeControls
                  player={player}
                  style={styles.video}
                />
              </View>
            </View>
          ) : null}

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Câmeras cadastradas</Text>

            {cameras.length === 0 ? (
              <Text style={styles.emptyText}>Nenhuma câmera cadastrada ainda.</Text>
            ) : (
              cameras.map((camera) => {
                const isSelected = selectedCameraId === camera.id;
                const isStarting = isStartingStreamId === camera.id;

                return (
                  <View
                    key={camera.id}
                    style={[styles.cameraCard, isSelected && styles.cameraCardActive]}
                  >
                    <View style={styles.cameraCardHeader}>
                      <View style={styles.cameraDetails}>
                        <Text style={styles.cameraTitle}>{camera.name}</Text>
                        <Text style={styles.cameraMeta}>
                          {getCameraHost(camera)} • {camera.status}
                        </Text>
                      </View>
                      <Pressable
                        disabled={isStarting}
                        onPress={() => handleStartStream(camera)}
                        style={[styles.secondaryButton, isStarting && styles.buttonDisabled]}
                      >
                        <Text style={styles.secondaryButtonText}>
                          {isStarting ? 'Abrindo...' : 'Ver ao vivo'}
                        </Text>
                      </Pressable>
                    </View>
                  </View>
                );
              })
            )}
          </View>
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: {
    paddingHorizontal: 18,
    paddingTop: 24,
    paddingBottom: 140,
    gap: 18,
  },
  header: {
    gap: 6,
  },
  title: {
    color: '#302611',
    fontSize: 28,
    lineHeight: 34,
    fontWeight: '800',
  },
  subtitle: {
    color: '#6F7B89',
    fontSize: 14,
    lineHeight: 20,
  },
  section: {
    backgroundColor: '#FFFFFF',
    borderRadius: 18,
    padding: 16,
    gap: 10,
    borderWidth: 1,
    borderColor: '#E8EEF4',
  },
  sectionTitle: {
    color: '#26303D',
    fontSize: 17,
    fontWeight: '800',
  },
  sectionHint: {
    color: '#7C8795',
    fontSize: 13,
    lineHeight: 18,
  },
  fieldLabel: {
    color: '#617084',
    fontSize: 13,
    fontWeight: '700',
  },
  input: {
    minHeight: 48,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#D9E4EF',
    paddingHorizontal: 14,
    backgroundColor: '#F8FBFE',
    color: '#26303D',
    fontSize: 14,
  },
  primaryButton: {
    minHeight: 50,
    borderRadius: 14,
    backgroundColor: '#019BDE',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 6,
  },
  buttonDisabled: {
    opacity: 0.7,
  },
  primaryButtonText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '800',
  },
  secondaryButton: {
    minWidth: 98,
    minHeight: 38,
    borderRadius: 12,
    backgroundColor: '#EAF7FF',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 12,
  },
  secondaryButtonText: {
    color: '#0A7FBA',
    fontSize: 13,
    fontWeight: '800',
  },
  errorText: {
    color: '#B24B3B',
    fontSize: 13,
    lineHeight: 18,
    fontWeight: '700',
  },
  emptyText: {
    color: '#7C8795',
    fontSize: 14,
  },
  centerState: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 48,
    gap: 10,
  },
  centerStateText: {
    color: '#6F7B89',
    fontSize: 14,
  },
  cameraCard: {
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#E3EAF2',
    padding: 14,
    backgroundColor: '#FBFDFF',
  },
  cameraCardActive: {
    borderColor: '#05BFE6',
    backgroundColor: '#F3FCFF',
  },
  cameraCardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  cameraDetails: {
    flex: 1,
  },
  cameraTitle: {
    color: '#26303D',
    fontSize: 15,
    fontWeight: '800',
  },
  cameraMeta: {
    color: '#7C8795',
    fontSize: 12,
    lineHeight: 16,
    marginTop: 2,
  },
  videoCard: {
    overflow: 'hidden',
    borderRadius: 16,
    backgroundColor: '#09131F',
  },
  video: {
    width: '100%',
    aspectRatio: 16 / 9,
  },
});
