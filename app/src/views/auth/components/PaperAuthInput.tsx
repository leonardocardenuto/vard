import { Feather } from '@expo/vector-icons';
import { GestureResponderEvent } from 'react-native';
import { TextInput } from 'react-native-paper';
import { KeyboardTypeOptions, TextInputProps } from "react-native";
import { styles } from '../auth_screen';

type PaperAuthInputProps = {
  testID?: string;
  label: string;
  onChangeText: (value: string) => void;
  value: string;
  editable?: boolean;
  keyboardType?: KeyboardTypeOptions;
  maxLength?: number;
  autoCapitalize?: TextInputProps["autoCapitalize"];
  onClear?: () => void;
  onPress?: (event: GestureResponderEvent) => void;
  rightIcon?: keyof typeof Feather.glyphMap;
  onToggleVisibility?: () => void;
  passwordVisible?: boolean;
  secureTextEntry?: boolean;
  selected?: boolean;
};

export function PaperAuthInput({
  testID,
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
  selected = false,
}: PaperAuthInputProps) {
  const isPassword = Boolean(onToggleVisibility);
  const activeColor = '#03CDF4';

  return (
    <TextInput
      testID={testID}
      autoCapitalize={autoCapitalize}
      editable={editable}
      keyboardType={keyboardType}
      label={label}
      mode="outlined"
      onPressIn={onPress}
      onChangeText={onChangeText}
      outlineColor={selected ? activeColor : '#C9C9C9'}
      activeOutlineColor={activeColor}
      placeholderTextColor="#B5B5B5"
      right={
        isPassword ? (
          <TextInput.Icon
            icon={() => <Feather color="#8D8D8D" name={passwordVisible ? 'eye-off' : 'eye'} size={17} />}
            onPress={onToggleVisibility}
          />
        ) : value && onClear ? (
          <TextInput.Icon icon={() => <Feather color={selected ? activeColor : '#777777'} name="x" size={16} />} onPress={onClear} />
        ) : rightIcon ? (
          <TextInput.Icon icon={() => <Feather color={selected ? activeColor : '#B5B5B5'} name={rightIcon} size={17} />} onPress={onPress} />
        ) : undefined
      }
      secureTextEntry={secureTextEntry}
      style={styles.paperInput}
      textColor="#333333"
      theme={{
        colors: {
          background: '#FFFFFF',
          onSurfaceVariant: selected ? activeColor : '#B0B0B0',
          primary: activeColor,
        },
        roundness: 12,
      }}
      value={value}
    />
  );
}
