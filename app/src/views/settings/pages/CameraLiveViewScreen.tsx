import { Feather } from '@expo/vector-icons';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useIsFocused } from '@react-navigation/native';
import { ActivityIndicator, Modal, Pressable, ScrollView, Text, View } from 'react-native';
import { useVideoPlayer, VideoView } from 'expo-video';
import { WebView } from 'react-native-webview';

import { LayoutWithNavbar } from '../../../components/LayoutWithNavbar';
import { decryptFallOccurredAt } from '../../../lib/fallHistoryCrypto';
import {
  prefetchFallEventClip,
  prepareFallEventClip,
  removePreparedFallEventClip,
} from '../../../lib/fallClipPlayback';
import { ApiRequestError, getMe, listFallEvents } from '../../../lib/api';
import { SettingsStackParamList } from '../types';
import { styles } from '../styles/CameraLiveViewScreen';
import { buildMjpegViewerHtml, CameraStreamState, isMjpegStreamUrl, parseCameraStreamMessage } from '../../../lib/cameraStream';

type Props = NativeStackScreenProps<SettingsStackParamList, 'CameraLiveView'>;

type CameraHistoryItem = {
  id: string;
  occurredAt: string;
  hasClip: boolean;
};

const CAMERA_WEBVIEW_INJECTED_JS = `
  (function() {
    if (window.__vardCameraMonitorInstalled) return;
    window.__vardCameraMonitorInstalled = true;
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
    var ready = false;
    function report(type) {
      if (window.ReactNativeWebView) window.ReactNativeWebView.postMessage(JSON.stringify({type:type}));
    }
    function checkMedia() {
      var images = Array.from(document.querySelectorAll('img'));
      var videos = Array.from(document.querySelectorAll('video'));
      videos.forEach(function(video){ video.controls=false; video.removeAttribute('controls'); });
      if (!ready && (images.some(function(image){return image.naturalWidth>0;}) || videos.some(function(video){return video.readyState>=2;}))) {
        ready=true; report('connected');
      }
    }
    document.addEventListener('error',function(event){if(event.target && /^(IMG|VIDEO)$/.test(event.target.tagName)) report('error');},true);
    var timer=setInterval(checkMedia,300);
    var timeout=setTimeout(function(){if(!ready)report('error');},15000);
    window.addEventListener('beforeunload',function(){clearInterval(timer);clearTimeout(timeout);});
  })();
  true;
`;

export function CameraLiveViewScreen({ navigation, route }: Props) {
  const { accessToken, cameraId, cameraName, protocol, url, workspaceId } = route.params;
  const player = useVideoPlayer(null);
  const clipPlayer = useVideoPlayer(null);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const [history, setHistory] = useState<CameraHistoryItem[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState(Boolean(accessToken && cameraId && workspaceId));
  const [loadingClipId, setLoadingClipId] = useState<string | null>(null);
  const [isClipVisible, setIsClipVisible] = useState(false);
  const [clipError, setClipError] = useState('');
  const [clipUri, setClipUri] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState('');
  const [streamState, setStreamState] = useState<CameraStreamState>('connecting');
  const [streamError, setStreamError] = useState('');
  const [retryCount, setRetryCount] = useState(0);
  const isFocused = useIsFocused();
  const focused = useRef(isFocused);
  focused.current = isFocused;
  useEffect(() => () => removePreparedFallEventClip(clipUri), [clipUri]);
  const isMjpeg = protocol === 'local-webview' && isMjpegStreamUrl(url);
  const webSource = useMemo(() => isMjpeg
    ? { html: buildMjpegViewerHtml(url) }
    : { uri: url, headers: protocol === 'agent-mjpeg' && accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined },
  [isMjpeg, url, protocol, accessToken]);

  function reportStreamState(next: CameraStreamState) {
    setStreamState(next);
    if (next === 'error') setStreamError('Não foi possível carregar a imagem. Verifique se a câmera está ligada e acessível nesta rede.');
    else setStreamError('');
    if (__DEV__) console.info('[camera-stream]', cameraId ?? cameraName, next);
  }

  useEffect(() => {
    setStreamState('connecting');
    setStreamError('');
  }, [url, protocol, retryCount, isFocused]);

  useEffect(() => {
    if (!accessToken || !cameraId || !workspaceId) {
      setHistory([]);
      setIsHistoryLoading(false);
      return;
    }

    let isMounted = true;
    setIsHistoryLoading(true);
    setHistoryError('');
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
          const firstClip = events.find((event) => event.camera_id === cameraId && event.has_clip);
          if (firstClip) prefetchFallEventClip(accessToken, firstClip.id);
        }
      } catch (error) {
        if (isMounted) {
          setHistory([]);
          setHistoryError(error instanceof ApiRequestError ? error.message : 'Não foi possível carregar o histórico desta câmera.');
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
    if (protocol !== 'hls' || !isFocused) {
      // Pause while the player is alive. useVideoPlayer releases it on
      // unmount, before this effect's cleanup runs.
      player.pause();
      return;
    }
    let active = true;
    async function syncPlayerSource() {
      try {
        await player.replaceAsync(url);
        if (active) player.play();
      } catch {
        if (active) {
          setStreamState('error');
          setStreamError('Não foi possível iniciar o vídeo desta câmera. Tente conectar novamente.');
        }
      }
    }

    void syncPlayerSource();
    const listener = player.addListener('statusChange', ({ status }) => {
      if (!active) return;
      if (status === 'readyToPlay') reportStreamState('connected');
      else if (status === 'error') reportStreamState('error');
      else reportStreamState('connecting');
    });
    return () => { active = false; listener.remove(); };
  }, [player, protocol, url, retryCount, isFocused]);

  async function openClip(event: CameraHistoryItem) {
    if (!accessToken || !event.hasClip || loadingClipId) return;

    setLoadingClipId(event.id);
    setClipError('');
    let prepared: string | null = null;
    try {
      prepared = await prepareFallEventClip(accessToken, event.id);
      if (!mounted.current || !focused.current) { removePreparedFallEventClip(prepared); return; }
      await clipPlayer.replaceAsync(prepared);
      if (!mounted.current || !focused.current) { removePreparedFallEventClip(prepared); return; }
      clipPlayer.play();
      setClipUri(prepared);
      setIsClipVisible(true);
    } catch (error) {
      removePreparedFallEventClip(prepared);
      if (!mounted.current || !focused.current) return;
      setClipError(
        error instanceof ApiRequestError
          ? error.status === 401
            ? 'Sua sessão expirou. Entre novamente para abrir o trecho.'
            : error.message
          : 'Não foi possível abrir o trecho da queda. Tente novamente.'
      );
    } finally {
      if (mounted.current) setLoadingClipId(null);
    }
  }

  async function closeClip() {
    if (!mounted.current) return;
    clipPlayer.pause();
    setIsClipVisible(false);
    if (clipUri) {
      removePreparedFallEventClip(clipUri);
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

        <View style={[styles.liveStatus, streamState !== 'connected' && styles.liveStatusInactive]}>
          <View style={[styles.liveDot, streamState !== 'connected' && styles.liveDotInactive]} />
          <Text style={[styles.liveStatusText, streamState !== 'connected' && styles.liveStatusTextInactive]}>
            {streamState === 'connected' ? 'Conectado' : streamState === 'connecting' ? 'Conectando…' : 'Sem imagem'}
          </Text>
        </View>

        <View style={styles.viewerCard}>
          {!isFocused ? null : protocol !== 'hls' ? (
            <WebView
              key={`${protocol}:${url}:${retryCount}`}
              injectedJavaScript={isMjpeg ? undefined : CAMERA_WEBVIEW_INJECTED_JS}
              injectedJavaScriptBeforeContentLoaded={isMjpeg ? undefined : CAMERA_WEBVIEW_INJECTED_JS}
              javaScriptEnabled
              originWhitelist={['*']}
              mixedContentMode="always"
              cacheEnabled={false}
              scalesPageToFit={false}
              source={webSource}
              onMessage={(event) => {
                const next = parseCameraStreamMessage(event.nativeEvent.data);
                if (next) reportStreamState(next);
              }}
              onError={() => reportStreamState('error')}
              onHttpError={() => reportStreamState('error')}
              onContentProcessDidTerminate={() => reportStreamState('error')}
              onRenderProcessGone={() => reportStreamState('error')}
              style={styles.webview}
            />
          ) : (
            <VideoView
              contentFit="cover"
              nativeControls={false}
              player={player}
              style={styles.video}
            />
          )}
          {streamState === 'connecting' ? (
            <View pointerEvents="none" style={styles.streamOverlay}>
              <ActivityIndicator color="#FFFFFF" />
              <Text style={styles.streamOverlayText}>Carregando imagem…</Text>
            </View>
          ) : null}
        </View>
        {streamError ? (
          <View style={styles.streamErrorPanel}>
            <Text accessibilityLiveRegion="polite" style={styles.streamErrorText}>{streamError}</Text>
            <Pressable accessibilityRole="button" onPress={() => setRetryCount((count) => count + 1)} style={styles.streamRetry}>
              <Feather name="refresh-cw" size={16} color="#FFFFFF" />
              <Text style={styles.streamRetryText}>Tentar novamente</Text>
            </Pressable>
          </View>
        ) : null}

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
            <ActivityIndicator color="#00B9BB" style={styles.historyLoading} />
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
                  <ActivityIndicator color="#00B9BB" />
                ) : event.hasClip ? (
                  <Feather color="#667085" name="play-circle" size={22} />
                ) : (
                  <Text style={styles.clipUnavailable}>Indisponível</Text>
                )}
              </Pressable>
            ))
          )}
          {historyError ? <Text style={styles.clipError}>{historyError}</Text> : null}
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
