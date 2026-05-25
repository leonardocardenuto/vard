import { LinearGradient } from 'expo-linear-gradient';
import { Pressable, Text } from 'react-native';

import { styles } from '../auth_screen';
import { AUTH_GRADIENT_COLORS, AUTH_GRADIENT_LOCATIONS } from '../types/flow';

type GradientButtonProps = {
  disabled?: boolean;
  label: string;
  onPress: () => void;
};

export function GradientButton({ disabled, label, onPress }: GradientButtonProps) {
  return (
    <Pressable
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [styles.gradientButton, (pressed || disabled) && styles.pressed]}
    >
      <LinearGradient
        colors={AUTH_GRADIENT_COLORS}
        locations={AUTH_GRADIENT_LOCATIONS}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.gradientButtonFill}
      >
        <Text style={styles.gradientButtonText}>{label}</Text>
      </LinearGradient>
    </Pressable>
  );
}
