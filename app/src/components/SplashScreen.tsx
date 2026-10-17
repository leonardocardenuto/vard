import { LinearGradient } from 'expo-linear-gradient';
import { StatusBar } from 'expo-status-bar';
import { StyleSheet, View } from 'react-native';

import VardLogo from '../../assets/vard_logo.svg';
import { VARD_GRADIENT } from '../theme/vardTheme';

export function SplashScreen() {
  return (
    <LinearGradient
      colors={VARD_GRADIENT}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
      style={styles.splashContainer}
    >
      <View style={styles.splashContent}>
        <VardLogo width={170} height={251} />
      </View>
      <StatusBar style="light" />
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  splashContainer: {
    flex: 1,
  },
  splashContent: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
