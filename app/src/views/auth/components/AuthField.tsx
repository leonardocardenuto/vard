import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import Feather from '@expo/vector-icons/Feather';

type AuthFieldProps = {
  label: string;
  onChangeText: (value: string) => void;
  placeholder: string;
  value: string;
  error?: string;
  autoCapitalize?: 'none' | 'sentences' | 'words' | 'characters';
  keyboardType?: 'default' | 'email-address' | 'phone-pad';
  onTogglePasswordVisibility?: () => void;
  passwordVisible?: boolean;
  secureTextEntry?: boolean;
  showPasswordToggle?: boolean;
};

export function AuthField({
  label,
  onChangeText,
  placeholder,
  value,
  error,
  autoCapitalize = 'sentences',
  keyboardType = 'default',
  onTogglePasswordVisibility,
  passwordVisible = false,
  secureTextEntry = false,
  showPasswordToggle = false,
}: AuthFieldProps) {
  return (
    <View style={styles.field}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <View style={[styles.inputWrap, error && styles.inputError]}>
        <TextInput
          key={showPasswordToggle ? `password-${passwordVisible ? 'visible' : 'hidden'}` : 'default'}
          autoCapitalize={autoCapitalize}
          keyboardType={keyboardType}
          onChangeText={onChangeText}
          placeholder={placeholder}
          placeholderTextColor="#C4BAA3"
          secureTextEntry={secureTextEntry}
          style={styles.input}
          value={value}
        />
        {showPasswordToggle ? (
          <Pressable
            hitSlop={10}
            onPress={onTogglePasswordVisibility}
            style={styles.passwordToggle}
          >
            <Feather
              color="#2E86BD"
              name={passwordVisible ? 'eye-off' : 'eye'}
              size={18}
            />
          </Pressable>
        ) : null}
      </View>
      {error ? <Text style={styles.fieldErrorText}>{error}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  field: {
    gap: 6,
  },
  fieldLabel: {
    color: '#746A52',
    fontSize: 13,
    fontWeight: '700',
  },
  inputWrap: {
    minHeight: 50,
    backgroundColor: '#F9EFD8',
    borderRadius: 20,
    paddingLeft: 18,
    paddingRight: 14,
    flexDirection: 'row',
    alignItems: 'center',
  },
  input: {
    flex: 1,
    color: '#40351D',
    fontSize: 14,
    fontWeight: '600',
  },
  inputError: {
    borderWidth: 1,
    borderColor: '#D36B5C',
  },
  passwordToggle: {
    paddingLeft: 10,
    paddingVertical: 8,
  },
  fieldErrorText: {
    color: '#B24B3B',
    fontSize: 12,
    lineHeight: 16,
    fontWeight: '700',
    paddingHorizontal: 6,
  },
});
