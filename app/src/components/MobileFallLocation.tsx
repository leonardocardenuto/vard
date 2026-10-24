import { useState } from 'react';
import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';
import { VARD_COLORS } from '../theme/vardTheme';
import { mobileFallCoordinates } from '../lib/mobileFallLocation';

export function MobileFallLocation({ payload, compact = false }: { payload: Record<string, unknown>; compact?: boolean }) {
  const [error, setError] = useState('');
  if (payload.source !== 'accelerometer') return null;
  const coordinates = mobileFallCoordinates(payload);
  if (!coordinates) return null;
  const { latitude, longitude } = coordinates;
  async function openMap() {
    setError('');
    try {
      await Linking.openURL(`https://www.google.com/maps/search/?api=1&query=${latitude},${longitude}`);
    } catch { setError('Não foi possível abrir o mapa. Tente novamente.'); }
  }
  return <View style={[styles.container, compact && styles.compactContainer]}>
    <Pressable accessibilityRole="link" accessibilityLabel="Ver localização da queda no mapa"
      onPress={() => void openMap()} style={styles.button}>
      <Text style={[styles.link, compact && styles.compactLink]}>Ver localização no mapa</Text>
    </Pressable>
    {error ? <Text accessibilityLiveRegion="polite" style={styles.error}>{error}</Text> : null}
  </View>;
}

const styles = StyleSheet.create({
  container: { gap: 4, marginVertical: 8 },
  compactContainer: { marginVertical: 0, flexShrink: 1 },
  compactLink: { fontSize: 11 },
  button: { minHeight: 44, justifyContent: 'center', alignSelf: 'flex-start' },
  link: { color: VARD_COLORS.secondary, fontFamily: 'Poppins-SemiBold', fontSize: 13 },
  error: { color: '#B42318', fontSize: 12 },
});
