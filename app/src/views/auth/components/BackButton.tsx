import { Feather } from '@expo/vector-icons';
import { Pressable, Text, View } from 'react-native';

import { styles } from '../auth_screen';
import { AuthGradientText } from './AuthGradientText';

type BackButtonProps = {
  gradientLabel?: boolean;
  label?: string;
  onPress: () => void;
};

export function BackButton({ gradientLabel = false, label, onPress }: BackButtonProps) {
  return (
    <View style={styles.backHeader}>
      <Pressable hitSlop={10} onPress={onPress} style={styles.backButton}>
        <Feather color="#101828" name="chevron-left" size={23} />
      </Pressable>
      {label && gradientLabel ? (
        <View style={styles.backLabelGradient}>
          <AuthGradientText
            fontFamily="Poppins-Medium"
            fontSize={14}
            height={21}
            text={label}
            textAnchor="middle"
            width={230}
            y={15}
          />
        </View>
      ) : label ? (
        <Text style={styles.backLabel}>{label}</Text>
      ) : null}
    </View>
  );
}
