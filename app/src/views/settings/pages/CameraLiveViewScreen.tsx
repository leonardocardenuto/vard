import { Feather } from '@expo/vector-icons';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Modal, Pressable, ScrollView, Text, View } from 'react-native';
import { useVideoPlayer, VideoView } from 'expo-video';
import * as FileSystem from 'expo-file-system/legacy';
import { WebView } from 'react-native-webview';

import { LayoutWithNavbar } from '../../../components/LayoutWithNavbar';
import { decryptFallClip, decryptFallOccurredAt } from '../../../lib/fallHistoryCrypto';
import { ApiRequestError, getFallEventClip, getMe, listFallEvents } from '../../../lib/api';
import { SettingsStackParamList } from '../types';
import { styles } from '../styles/CameraLiveViewScreen';

type Props = NativeStackScreenProps<SettingsStackParamList, 'CameraLiveView'>;

type CameraHistoryItem = {
  id: string;
  occurredAt: string;
  hasClip: boolean;
};

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

export function CameraLiveViewScreen({ navigation, route }: Props) {
  const { accessToken, cameraId, cameraName, protocol, url, workspaceId } = route.params;
  const player = useVideoPlayer(null);
  const clipPlayer = useVideoPlayer(null);
  const [history, setHistory] = useState<CameraHistoryItem[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState(Boolean(accessToken && cameraId && workspaceId));
  const [loadingClipId, setLoadingClipId] = useState<string | null>(null);
  const [isClipVisible, setIsClipVisible] = useState(false);
  const [clipError, setClipError] = useState('');
  const [clipUri, setClipUri] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken || !cameraId || !workspaceId) {
      setHistory([]);
      setIsHistoryLoading(false);
      return;
    }

    let isMounted = true;
    void (async () => {
      try {
        const [me, events] = await Promise.all([
          getMe(accessToken),
          listFallEvents(accessToken, workspaceId),
        ]);
        const items = await Promise.all(
          events
            .filter((event) => event.camera_id === cameraId)
            .map(async (event) => ({
              id: event.id,
              occurredAt: await decryptFallOccurredAt(event.encrypted_payload, event.key_envelope, me.id),
              hasClip: event.has_clip,
            }))
        );
        if (isMounted) {
          setHistory(
            items
              .filter((item): item is CameraHistoryItem => Boolean(item.occurredAt))
              .sort((left, right) => right.occurredAt.localeCompare(left.occurredAt))
          );
        }
      } finally {
        if (isMounted) setIsHistoryLoading(false);
      }
    })();

    return () => {
      isMounted = false;
    };
  }, [accessToken, cameraId, workspaceId]);

  useEffect(() => {
    async function syncPlayerSource() {
      if (protocol !== 'hls') {
        return;
      }

      try {
        await player.replaceAsync(url);
        player.play();
      } catch {
        // caller already handles the failure state
      }
    }

    void syncPlayerSource();
  }, [player, protocol, url]);

  async function openClip(event: CameraHistoryItem) {
    if (!accessToken || !event.hasClip || loadingClipId) return;

    setLoadingClipId(event.id);
    setClipError('');
    try {
      const [me, clip] = await Promise.all([getMe(accessToken), getFallEventClip(accessToken, event.id)]);
      const decryptedClip = await decryptFallClip(clip.encrypted_clip, clip.key_envelope, me.id);
      if (!decryptedClip || !FileSystem.cacheDirectory) throw new Error('Não foi possível abrir o trecho.');

      const clipUri = `${FileSystem.cacheDirectory}vard-fall-${event.id}.mp4`;
      await FileSystem.writeAsStringAsync(clipUri, bytesToBase64(decryptedClip), {
        encoding: FileSystem.EncodingType.Base64,
      });
      await clipPlayer.replaceAsync(clipUri);
      clipPlayer.play();
      setClipUri(clipUri);
      setIsClipVisible(true);
    } catch (error) {
      setClipError(
        error instanceof ApiRequestError && error.status === 401
          ? 'Sua sessão expirou. Entre novamente para abrir o trecho.'
          : 'Não foi possível abrir o trecho da queda. Tente novamente.'
      );
    } finally {
      setLoadingClipId(null);
    }
  }

  async function closeClip() {
    clipPlayer.pause();
    setIsClipVisible(false);
    if (clipUri) {
      await FileSystem.deleteAsync(clipUri, { idempotent: true });
      setClipUri(null);
    }
  }

  return (
    <LayoutWithNavbar>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.topSpacer} />

        <View style={styles.headerRow}>
          <Pressable onPress={() => navigation.goBack()} style={styles.backButton}>
            <Feather color="#344054" name="arrow-left" size={20} />
          </Pressable>
          <View style={styles.headerText}>
            <Text style={styles.headerEyebrow}>MONITOR AO VIVO</Text>
            <Text numberOfLines={1} style={styles.headerTitle}>
              {cameraName}
            </Text>
          </View>
          <View style={styles.headerBalance} />
        </View>

        <View style={styles.liveStatus}>
          <View style={styles.liveDot} />
          <Text style={styles.liveStatusText}>Conectado</Text>
        </View>

        <View style={styles.viewerCard}>
          {protocol === 'local-webview' ? (
            <WebView
              injectedJavaScript={CAMERA_WEBVIEW_INJECTED_JS}
              injectedJavaScriptBeforeContentLoaded={CAMERA_WEBVIEW_INJECTED_JS}
              javaScriptEnabled
              scalesPageToFit={false}
              source={{ uri: url }}
              startInLoadingState
              style={styles.webview}
            />
          ) : protocol === 'agent-mjpeg' ? (
            <WebView
              injectedJavaScript={CAMERA_WEBVIEW_INJECTED_JS}
              injectedJavaScriptBeforeContentLoaded={CAMERA_WEBVIEW_INJECTED_JS}
              javaScriptEnabled
              scalesPageToFit={false}
              source={{ uri: url, headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined }}
              startInLoadingState
              style={styles.webview}
            />
          ) : (
            <VideoView
              contentFit="cover"
              nativeControls
              player={player}
              style={styles.video}
            />
          )}
        </View>

        <View style={styles.historySection}>
          <View style={styles.historyHeader}>
            <View>
              <Text style={styles.historyTitle}>Histórico desta câmera</Text>
            </View>
            <View style={styles.historyCount}>
              <Text style={styles.historyCountText}>{history.length}</Text>
            </View>
          </View>

          {isHistoryLoading ? (
            <ActivityIndicator color="#019BDE" style={styles.historyLoading} />
          ) : history.length === 0 ? (
            <Text style={styles.emptyHistory}>Nenhum evento de queda registrado nesta câmera.</Text>
          ) : (
            history.slice(0, 5).map((event) => (
              <Pressable
                accessibilityLabel={`Abrir trecho da queda em ${formatHistoryDate(event.occurredAt)}`}
                accessibilityRole="button"
                disabled={!event.hasClip || Boolean(loadingClipId)}
                key={event.id}
                onPress={() => void openClip(event)}
                style={({ pressed }) => [
                  styles.historyItem,
                  !event.hasClip && styles.historyItemDisabled,
                  pressed && styles.historyItemPressed,
                ]}
              >
                <View style={styles.historyIcon}>
                  <Feather color="#D92D20" name="alert-triangle" size={16} />
                </View>
                <View style={styles.historyText}>
                  <Text style={styles.historyItemTitle}>Queda</Text>
                  <Text style={styles.historyItemDate}>{formatHistoryDate(event.occurredAt)}</Text>
                </View>
                {loadingClipId === event.id ? (
                  <ActivityIndicator color="#019BDE" />
                ) : event.hasClip ? (
                  <Feather color="#667085" name="play-circle" size={22} />
                ) : (
                  <Text style={styles.clipUnavailable}>Indisponível</Text>
                )}
              </Pressable>
            ))
          )}
          {clipError ? <Text style={styles.clipError}>{clipError}</Text> : null}
        </View>
      </ScrollView>

      <Modal animationType="slide" onRequestClose={() => void closeClip()} transparent visible={isClipVisible}>
        <View style={styles.clipModalBackdrop}>
          <View style={styles.clipModalCard}>
            <View style={styles.clipModalHeader}>
              <View>
                <Text style={styles.clipModalEyebrow}>HISTÓRICO DE QUEDAS</Text>
                <Text style={styles.clipModalTitle}>Trecho da queda</Text>
              </View>
              <Pressable accessibilityLabel="Fechar vídeo" onPress={() => void closeClip()} style={styles.clipCloseButton}>
                <Feather color="#344054" name="x" size={21} />
              </Pressable>
            </View>
            <VideoView contentFit="contain" nativeControls player={clipPlayer} style={styles.clipVideo} />
          </View>
        </View>
      </Modal>
    </LayoutWithNavbar>
  );
}

function formatHistoryDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? 'Horário protegido'
    : date.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
}

function bytesToBase64(value: Uint8Array) {
  const chunkSize = 0x8000;
  let binary = '';
  for (let index = 0; index < value.length; index += chunkSize) {
    binary += String.fromCharCode(...value.subarray(index, index + chunkSize));
  }
  return btoa(binary);
}
