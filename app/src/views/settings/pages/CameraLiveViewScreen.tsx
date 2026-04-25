import { Feather } from '@expo/vector-icons';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useEffect } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useVideoPlayer, VideoView } from 'expo-video';
import { WebView } from 'react-native-webview';

import { LayoutWithNavbar } from '../../../components/LayoutWithNavbar';
import { SettingsStackParamList } from '../types';

type Props = NativeStackScreenProps<SettingsStackParamList, 'CameraLiveView'>;

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
        // caller already handles the failure state
      }
    }

    void syncPlayerSource();
  }, [player, protocol, url]);

  return (
    <LayoutWithNavbar>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.topSpacer} />

        <View style={styles.headerRow}>
          <Pressable onPress={() => navigation.goBack()} style={styles.backButton}>
            <Feather color="#111827" name="chevron-left" size={20} />
          </Pressable>
          <View style={styles.headerText}>
            <Text numberOfLines={1} style={styles.headerTitle}>
              {cameraName}
            </Text>
            <Text style={styles.headerSubtitle}>Camera ao vivo</Text>
          </View>
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
          ) : (
            <VideoView
              contentFit="cover"
              nativeControls
              player={player}
              style={styles.video}
            />
          )}
        </View>
      </ScrollView>
    </LayoutWithNavbar>
  );
}

const styles = StyleSheet.create({
  content: {
    paddingHorizontal: 22,
    paddingBottom: 144,
  },
  topSpacer: {
    height: 56,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 18,
  },
  backButton: {
    width: 32,
    height: 32,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerText: {
    flex: 1,
  },
  headerTitle: {
    color: '#111827',
    fontSize: 22,
    fontWeight: '800',
  },
  headerSubtitle: {
    marginTop: 4,
    color: '#667085',
    fontSize: 14,
  },
  viewerCard: {
    overflow: 'hidden',
    borderRadius: 20,
    backgroundColor: '#09131F',
    height: 520,
  },
  video: {
    width: '100%',
    height: '100%',
  },
  webview: {
    width: '100%',
    height: '100%',
    backgroundColor: '#000000',
  },
});
