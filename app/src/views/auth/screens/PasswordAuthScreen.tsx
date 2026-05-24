import { Pressable, ScrollView, Text } from 'react-native';

import { AuthGradientText } from '../components/AuthGradientText';
import { BackButton } from '../components/BackButton';
import { GradientButton } from '../components/GradientButton';
import { PaperAuthInput } from '../components/PaperAuthInput';
import { styles } from '../auth_screen';

type PasswordAuthScreenProps = {
  errorMessage: string;
  isPasswordVisible: boolean;
  isSubmitting: boolean;
  onBack: () => void;
  onChangePassword: (value: string) => void;
  onContinue: () => void;
  onTogglePassword: () => void;
  password: string;
};

export function PasswordAuthScreen({
  errorMessage,
  isPasswordVisible,
  isSubmitting,
  onBack,
  onChangePassword,
  onContinue,
  onTogglePassword,
  password,
}: PasswordAuthScreenProps) {
  return (
    <ScrollView contentContainerStyle={styles.passwordContent} keyboardShouldPersistTaps="handled">
      <BackButton onPress={onBack} />
      <AuthGradientText
        fontSize={34}
        fontFamily="Poppins-SemiBold"
        height={76}
        lineHeight={35}
        text={'Bem-Vindo\nde volta!'}
        width={300}
        y={32}
      />
      <Text style={styles.bodyText}>Nos achamos uma conta vinculada a este email. Por favor, insira sua senha.</Text>

      <PaperAuthInput
        label="Senha"
        onChangeText={onChangePassword}
        onToggleVisibility={onTogglePassword}
        passwordVisible={isPasswordVisible}
        secureTextEntry={!isPasswordVisible}
        value={password}
      />

      {errorMessage ? <Text style={styles.errorText}>{errorMessage}</Text> : null}

      <GradientButton disabled={isSubmitting} label={isSubmitting ? 'ENTRANDO...' : 'CONTINUE'} onPress={onContinue} />

      <Pressable style={styles.resetButton}>
        <Text style={styles.resetText}>REDEFINIR SENHA</Text>
      </Pressable>
    </ScrollView>
  );
}
