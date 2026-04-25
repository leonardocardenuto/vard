import { Feather, MaterialCommunityIcons } from '@expo/vector-icons';
import { useFocusEffect, useNavigation } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useCallback, useEffect, useState } from 'react';
import { useVideoPlayer, VideoView } from 'expo-video';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { ApiRequestError, CameraResponse, listCameras, startCameraHlsStream, WorkspaceResponse } from '../../../lib/api';
import { SettingsStackParamList } from '../types';
import { resolvePrimaryWorkspace } from '../utils/resolveWorkspace';

type CameraSettingsPanelProps = {
  accessToken: string;
  userEmail: string;
  userName: string;
};

type SettingsNavigation = NativeStackNavigationProp<SettingsStackParamList, 'SettingsHome'>;

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
            'body > * { max-width: 100% !important; }',
            'iframe, video, img, canvas, object, embed { width: 100% !important; height: 100% !important; max-width: 100% !important; max-height: 100% !important; object-fit: contain !important; display: block !important; margin: 0 !important; padding: 0 !important; }',
            '[style*="width"], [style*="height"] { max-width: 100% !important; }'
          ].join('');
          document.head.appendChild(style);
        }

        document.documentElement.style.width = '100%';
        document.documentElement.style.height = '100%';
        document.body.style.width = '100%';
        document.body.style.height = '100%';
        document.body.style.margin = '0';
        document.body.style.padding = '0';
        document.body.style.overflow = 'hidden';

        var nodes = document.querySelectorAll('iframe, video, img, canvas, object, embed');
        nodes.forEach(function(node) {
          node.style.width = '100%';
          node.style.height = '100%';
          node.style.maxWidth = '100%';
          node.style.maxHeight = '100%';
          node.style.display = 'block';
          node.style.margin = '0';
          node.style.padding = '0';
        });
      } catch (error) {}
    }

    applyFullscreenStyles();
    setTimeout(applyFullscreenStyles, 300);
    setTimeout(applyFullscreenStyles, 1000);
    setInterval(applyFullscreenStyles, 2000);
  })();
  true;
`;

function getCameraMetadata(camera: CameraResponse) {
  return camera.metadata ?? camera.metadata_json ?? {};
}

function getCameraStatusLabel(camera: CameraResponse) {
  return camera.status === 'online' ? 'Online' : 'Offline';
}

function getCameraProtocol(camera: CameraResponse) {
  const metadata = getCameraMetadata(camera);
  const protocol = typeof metadata.protocol === 'string' ? metadata.protocol : camera.connection_type;

  if (protocol === 'local-webview') {
    return 'Local';
  }

  if (protocol === 'https' || protocol === 'https-manual') {
    return 'HTTPS';
  }

  return 'RTSP';
}

export function CameraSettingsPanel({
  accessToken,
  userEmail,
  userName,
}: CameraSettingsPanelProps) {
  const navigation = useNavigation<SettingsNavigation>();
  const player = useVideoPlayer(null);

  const [workspace, setWorkspace] = useState<WorkspaceResponse | null>(null);
  const [cameras, setCameras] = useState<CameraResponse[]>([]);
  const [isBootstrapping, setIsBootstrapping] = useState(true);
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
        setErrorMessage('Nao foi possivel carregar o video ao vivo.');
      }
    }

    void syncPlayerSource();
  }, [player, streamUrl]);

  const loadDevices = useCallback(async () => {
    if (!accessToken) {
      setErrorMessage('Sessao invalida. Faca login novamente.');
      setIsBootstrapping(false);
      return;
    }

    try {
      setErrorMessage('');
      setIsBootstrapping(true);

      const resolvedWorkspace = await resolvePrimaryWorkspace({
        accessToken,
        userEmail,
        userName,
      });
      const workspaceCameras = await listCameras(accessToken, resolvedWorkspace.id);

      setWorkspace(resolvedWorkspace);
      setCameras(workspaceCameras);
    } catch (error) {
      setErrorMessage(
        error instanceof ApiRequestError ? error.message : 'Nao foi possivel carregar os ajustes.'
      );
    } finally {
      setIsBootstrapping(false);
    }
  }, [accessToken, userEmail, userName]);

  useEffect(() => {
    void loadDevices();
  }, [loadDevices]);

  useFocusEffect(
    useCallback(() => {
      void loadDevices();
    }, [loadDevices])
  );

  async function handleStartStream(camera: CameraResponse) {
    const metadata = getCameraMetadata(camera);
    const protocol = typeof metadata.protocol === 'string' ? metadata.protocol : camera.connection_type;

    if (protocol === 'local-webview') {
      setSelectedCameraId(camera.id);
      setStreamUrl('');
      navigation.navigate('CameraLiveView', {
        cameraName: camera.name,
        protocol: 'local-webview',
        url: camera.stream_url,
      });
      return;
    }

    setIsStartingStreamId(camera.id);
    setErrorMessage('');

    try {
      const response = await startCameraHlsStream(accessToken, camera.id);
      setSelectedCameraId(camera.id);
      setStreamUrl(response.playlist_url);
      navigation.navigate('CameraLiveView', {
        cameraName: camera.name,
        protocol: 'hls',
        url: response.playlist_url,
      });
    } catch (error) {
      setErrorMessage(
        error instanceof ApiRequestError
          ? error.message
          : 'Nao foi possivel iniciar o stream da camera.'
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
        <View style={styles.futureHeaderSpace} />
        <Text style={styles.title}>Ajustes do Sistema</Text>
        <Text style={styles.subtitle}>
          Gerencie seus dispositivos e preferencias de seguranca
        </Text>
        {workspace ? <Text style={styles.workspaceName}>{workspace.name}</Text> : null}
      </View>

      {isBootstrapping ? (
        <View style={styles.centerState}>
          <ActivityIndicator color="#0BA5EC" />
          <Text style={styles.centerStateText}>Carregando dispositivos...</Text>
        </View>
      ) : (
        <>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Dispositivos conectados</Text>
            <Pressable
              accessibilityRole="button"
              onPress={() =>
                navigation.navigate('CameraConnectionForm', {
                  accessToken,
                  userEmail,
                  userName,
                })
              }
              style={styles.addButton}
            >
              <Feather color="#121926" name="plus" size={18} />
            </Pressable>
          </View>

          {errorMessage ? <Text style={styles.errorText}>{errorMessage}</Text> : null}

          {cameras.length === 0 ? (
            <View style={styles.emptyCard}>
              <Text style={styles.emptyTitle}>Nenhum dispositivo conectado</Text>
              <Text style={styles.emptySubtitle}>
                Toque no + para cadastrar sua primeira camera.
              </Text>
            </View>
          ) : (
            cameras.map((camera) => {
              const isSelected = selectedCameraId === camera.id;
              const isStarting = isStartingStreamId === camera.id;

              return (
                <Pressable
                  key={camera.id}
                  disabled={isStarting}
                  onPress={() => handleStartStream(camera)}
                  style={[styles.deviceCard, isSelected && styles.deviceCardActive]}
                >
                  <View style={styles.deviceIconWrap}>
                    <MaterialCommunityIcons color="#00B6FF" name="cctv" size={24} />
                  </View>

                  <View style={styles.deviceContent}>
                    <Text numberOfLines={2} style={styles.deviceName}>
                      {camera.name}
                    </Text>
                    <Text style={styles.deviceProtocol}>{getCameraProtocol(camera)}</Text>
                    <View style={styles.statusRow}>
                      <View
                        style={[
                          styles.statusDot,
                          camera.status === 'online'
                            ? styles.statusDotOnline
                            : styles.statusDotOffline,
                        ]}
                      />
                      <Text
                        style={[
                          styles.statusText,
                          camera.status === 'online'
                            ? styles.statusTextOnline
                            : styles.statusTextOffline,
                        ]}
                      >
                        {isStarting ? 'Conectando...' : getCameraStatusLabel(camera)}
                      </Text>
                    </View>
                  </View>

                  <Feather color="#667085" name="chevron-right" size={18} />
                </Pressable>
              );
            })
          )}

          {streamUrl ? (
            <View style={styles.streamSection}>
              <Text style={styles.streamTitle}>Preview ao vivo</Text>
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
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: {
    paddingHorizontal: 22,
    paddingTop: 24,
    paddingBottom: 144,
  },
  header: {
    marginBottom: 28,
  },
  futureHeaderSpace: {
    height: 56,
  },
  title: {
    color: '#0694EA',
    fontSize: 22,
    lineHeight: 28,
    fontWeight: '800',
  },
  subtitle: {
    marginTop: 4,
    color: '#667085',
    fontSize: 14,
    lineHeight: 20,
  },
  workspaceName: {
    marginTop: 10,
    color: '#101828',
    fontSize: 13,
    fontWeight: '700',
  },
  centerState: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 72,
    gap: 10,
  },
  centerStateText: {
    color: '#667085',
    fontSize: 14,
  },
  sectionHeader: {
    marginBottom: 14,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  sectionTitle: {
    color: '#101828',
    fontSize: 18,
    lineHeight: 24,
    fontWeight: '700',
  },
  addButton: {
    width: 28,
    height: 28,
    alignItems: 'center',
    justifyContent: 'center',
  },
  errorText: {
    marginBottom: 14,
    color: '#B42318',
    fontSize: 13,
    lineHeight: 18,
    fontWeight: '600',
  },
  emptyCard: {
    borderRadius: 20,
    backgroundColor: '#FFFFFF',
    padding: 18,
    shadowColor: '#101828',
    shadowOpacity: 0.05,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 8 },
    elevation: 2,
  },
  emptyTitle: {
    color: '#101828',
    fontSize: 15,
    fontWeight: '700',
  },
  emptySubtitle: {
    marginTop: 6,
    color: '#667085',
    fontSize: 14,
    lineHeight: 20,
  },
  deviceCard: {
    marginBottom: 14,
    borderRadius: 20,
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 14,
    paddingVertical: 16,
    flexDirection: 'row',
    alignItems: 'center',
    shadowColor: '#101828',
    shadowOpacity: 0.05,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 8 },
    elevation: 2,
  },
  deviceCardActive: {
    borderWidth: 1,
    borderColor: '#9BDAF8',
  },
  deviceIconWrap: {
    width: 28,
    alignItems: 'flex-start',
    justifyContent: 'center',
  },
  deviceContent: {
    flex: 1,
    paddingHorizontal: 10,
  },
  deviceName: {
    color: '#111827',
    fontSize: 17,
    lineHeight: 23,
    fontWeight: '700',
  },
  statusRow: {
    marginTop: 6,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  deviceProtocol: {
    marginTop: 4,
    color: '#667085',
    fontSize: 12,
    fontWeight: '600',
  },
  statusDot: {
    width: 7,
    height: 7,
    borderRadius: 999,
  },
  statusDotOnline: {
    backgroundColor: '#12B76A',
  },
  statusDotOffline: {
    backgroundColor: '#98A2B3',
  },
  statusText: {
    fontSize: 13,
    fontWeight: '600',
  },
  statusTextOnline: {
    color: '#12B76A',
  },
  statusTextOffline: {
    color: '#667085',
  },
  streamSection: {
    marginTop: 10,
    gap: 12,
  },
  streamTitle: {
    color: '#101828',
    fontSize: 16,
    fontWeight: '700',
  },
  videoCard: {
    overflow: 'hidden',
    borderRadius: 20,
    backgroundColor: '#09131F',
    height: 260,
  },
  video: {
    width: '100%',
    height: '100%',
  },
});
