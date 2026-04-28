import { LinearGradient } from 'expo-linear-gradient';
import { StatusBar } from 'expo-status-bar';
import { StyleSheet, View } from 'react-native';

import VardLogo from '../../assets/vard_logo.svg';

export function SplashScreen() {
  return (
    <LinearGradient
      colors={['#03CDF4', '#019BDE', '#01EBD0']}
      locations={[0.01, 0.48, 1]}
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
