import { FontAwesome5 } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { Image, Pressable, Text, View } from 'react-native';

import { styles } from '../auth_screen';
import { AUTH_GRADIENT_COLORS, AUTH_GRADIENT_LOCATIONS } from '../types/flow';

type LandingAuthScreenProps = {
  onAccessAccount: () => void;
};

export function LandingAuthScreen({ onAccessAccount }: LandingAuthScreenProps) {
  return (
    <View style={styles.landing}>
      <Image
        resizeMode="cover"
        source={require('../../../../assets/wallpapervard.png')}
        style={styles.landingImage}
      />
      <LinearGradient
        colors={AUTH_GRADIENT_COLORS}
        locations={AUTH_GRADIENT_LOCATIONS}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.emergencyPanel}
      >
        <View style={styles.emergencyRow}>
          <EmergencyItem icon="asterisk" label="SAMU" />
          <View style={styles.emergencyDivider} />
          <EmergencyItem icon="shield-alt" label="POLICIA" />
          <View style={styles.emergencyDivider} />
          <EmergencyItem icon="fire-alt" label="BOMBEIRO" />
        </View>

        <Pressable onPress={onAccessAccount} style={({ pressed }) => [styles.whiteButton, pressed && styles.pressed]}>
          <Text style={styles.whiteButtonText}>ACESSAR SUA CONTA</Text>
        </Pressable>
      </LinearGradient>
    </View>
  );
}

function EmergencyItem({ icon, label }: { icon: keyof typeof FontAwesome5.glyphMap; label: string }) {
  return (
    <View style={styles.emergencyItem}>
      <FontAwesome5 color="#FFFFFF" name={icon} size={17} />
      <Text style={styles.emergencyLabel}>{label}</Text>
    </View>
  );
}
