import { Feather } from '@expo/vector-icons';
import { useVideoPlayer, VideoView } from 'expo-video';
import { useEffect, useRef, useState } from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { prepareFallEventClip, removePreparedFallEventClip } from '../lib/fallClipPlayback';

export function useOccurrenceClip(accessToken: string) {
  const player = useVideoPlayer(null);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [uri, setUri] = useState<string | null>(null);
  const [error, setError] = useState('');
  const busy = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => () => removePreparedFallEventClip(uri), [uri]);

  async function openClip(eventId: string) {
    if (busy.current) return;
    busy.current = true; setLoadingId(eventId); setError('');
    let prepared: string | null = null;
    try {
      prepared = await prepareFallEventClip(accessToken, eventId);
      if (!mounted.current) { removePreparedFallEventClip(prepared); return; }
      await player.replaceAsync(prepared);
      if (!mounted.current) { removePreparedFallEventClip(prepared); return; }
      player.play(); setUri(prepared);
    } catch (error) {
      removePreparedFallEventClip(prepared);
      if (mounted.current) setError(error instanceof Error ? error.message : 'Não foi possível reproduzir o trecho neste celular.');
    } finally { busy.current = false; if (mounted.current) setLoadingId(null); }
  }
  function close() { if (!mounted.current) return; player.pause(); setUri(null); }

  const clipModal = <Modal transparent animationType="fade" visible={Boolean(uri)} onRequestClose={close}>
    <View style={styles.backdrop}>
      <View style={styles.modal}>
        <View style={styles.header}>
          <Text style={styles.title}>Trecho da queda</Text>
          <Pressable accessibilityRole="button" accessibilityLabel="Fechar vídeo" onPress={close} style={styles.close}>
            <Feather name="x" color="#344054" size={21} />
          </Pressable>
        </View>
        <VideoView player={player} style={styles.video} nativeControls contentFit="contain" />
      </View>
    </View>
  </Modal>;
  return { openClip, loadingId, error, clipModal };
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(16,24,40,0.72)', alignItems: 'center', justifyContent: 'center', padding: 20 },
  modal: { width: '100%', maxWidth: 560, backgroundColor: '#FFF', borderRadius: 20, padding: 16 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  title: { fontFamily: 'Poppins-SemiBold', fontSize: 18, color: '#101828' },
  close: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  video: { width: '100%', aspectRatio: 16 / 9, backgroundColor: '#000', borderRadius: 12 },
});
