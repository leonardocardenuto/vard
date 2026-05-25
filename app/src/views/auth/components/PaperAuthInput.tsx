import { Feather } from '@expo/vector-icons';
import { GestureResponderEvent } from 'react-native';
import { TextInput } from 'react-native-paper';

import { styles } from '../auth_screen';

type PaperAuthInputProps = {
  label: string;
  onChangeText: (value: string) => void;
  value: string;
  autoCapitalize?: 'none' | 'sentences' | 'words' | 'characters';
  editable?: boolean;
  keyboardType?: 'default' | 'email-address';
  onClear?: () => void;
  onPress?: (event: GestureResponderEvent) => void;
  rightIcon?: keyof typeof Feather.glyphMap;
  onToggleVisibility?: () => void;
  passwordVisible?: boolean;
  secureTextEntry?: boolean;
};

export function PaperAuthInput({
  label,
  onChangeText,
  value,
  autoCapitalize = 'sentences',
  editable = true,
  keyboardType = 'default',
  onClear,
  onPress,
  rightIcon,
  onToggleVisibility,
  passwordVisible = false,
  secureTextEntry = false,
}: PaperAuthInputProps) {
  const isPassword = Boolean(onToggleVisibility);

  return (
    <TextInput
      autoCapitalize={autoCapitalize}
      editable={editable}
      keyboardType={keyboardType}
      label={label}
      mode="outlined"
      onPressIn={onPress}
      onChangeText={onChangeText}
      outlineColor="#C9C9C9"
      activeOutlineColor="#03CDF4"
      placeholderTextColor="#B5B5B5"
      right={
        isPassword ? (
          <TextInput.Icon
            icon={() => <Feather color="#8D8D8D" name={passwordVisible ? 'eye-off' : 'eye'} size={17} />}
            onPress={onToggleVisibility}
          />
        ) : value && onClear ? (
          <TextInput.Icon icon={() => <Feather color="#777777" name="x" size={16} />} onPress={onClear} />
        ) : rightIcon ? (
          <TextInput.Icon icon={() => <Feather color="#B5B5B5" name={rightIcon} size={17} />} onPress={onPress} />
        ) : undefined
      }
      secureTextEntry={secureTextEntry}
      style={styles.paperInput}
      textColor="#333333"
      theme={{
        colors: {
          background: '#FFFFFF',
          onSurfaceVariant: '#B0B0B0',
          primary: '#03CDF4',
        },
        roundness: 12,
      }}
      value={value}
    />
  );
}
