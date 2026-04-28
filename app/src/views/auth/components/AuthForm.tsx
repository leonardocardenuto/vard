import { Pressable, StyleSheet, Text, View } from 'react-native';

import { AuthField } from './AuthField';
import { AuthFormErrors, AuthFormState, AuthMode } from '../types/auth';

type AuthFormProps = {
  fieldErrors: AuthFormErrors;
  form: AuthFormState;
  isPasswordVisible: boolean;
  mode: AuthMode;
  onTogglePasswordVisibility: () => void;
  onUpdateField: (field: keyof AuthFormState, value: string) => void;
};

export function AuthForm({
  fieldErrors,
  form,
  isPasswordVisible,
  mode,
  onTogglePasswordVisibility,
  onUpdateField,
}: AuthFormProps) {
  const isSignup = mode === 'signup';

  return (
    <View style={styles.form}>
      {isSignup ? (
        <>
          <AuthField
            error={fieldErrors.fullName}
            label="Nome completo"
            onChangeText={(value) => onUpdateField('fullName', value)}
            placeholder="Ex.: Evelyn Harper"
            value={form.fullName}
          />
          <AuthField
            autoCapitalize="none"
            error={fieldErrors.email}
            keyboardType="email-address"
            label="Endereço de e-mail"
            onChangeText={(value) => onUpdateField('email', value)}
            placeholder="você@familia.com"
            value={form.email}
          />
          <AuthField
            error={fieldErrors.phone}
            keyboardType="phone-pad"
            label="Telefone"
            onChangeText={(value) => onUpdateField('phone', value)}
            placeholder="(11) 99999-0000"
            value={form.phone}
          />
          <AuthField
            error={fieldErrors.password}
            label="Senha"
            onChangeText={(value) => onUpdateField('password', value)}
            placeholder="Crie uma senha segura"
            onTogglePasswordVisibility={onTogglePasswordVisibility}
            passwordVisible={isPasswordVisible}
            secureTextEntry={!isPasswordVisible}
            showPasswordToggle
            value={form.password}
          />
        </>
      ) : (
        <>
          <AuthField
            autoCapitalize="none"
            error={fieldErrors.email}
            keyboardType="email-address"
            label="Endereço de e-mail"
            onChangeText={(value) => onUpdateField('email', value)}
            placeholder="você@familia.com"
            value={form.email}
          />
          <AuthField
            error={fieldErrors.password}
            label="Senha"
            onChangeText={(value) => onUpdateField('password', value)}
            placeholder="Sua senha"
            onTogglePasswordVisibility={onTogglePasswordVisibility}
            passwordVisible={isPasswordVisible}
            secureTextEntry={!isPasswordVisible}
            showPasswordToggle
            value={form.password}
          />
          <Pressable style={styles.inlineAction}>
            <Text style={styles.inlineActionText}>Esqueci minha senha</Text>
          </Pressable>
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  form: {
    gap: 12,
  },
  inlineAction: {
    alignSelf: 'flex-end',
    marginTop: -4,
  },
  inlineActionText: {
    color: '#2E86BD',
    fontSize: 13,
    fontWeight: '700',
  },
});
