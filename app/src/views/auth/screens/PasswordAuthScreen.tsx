import { Pressable, ScrollView, Text, View } from "react-native";
import { AuthGradientText } from "../components/AuthGradientText";
import { BackButton } from "../components/BackButton";
import { GradientButton } from "../components/GradientButton";
import { PaperAuthInput } from "../components/PaperAuthInput";
import { styles } from "../auth_screen";

type PasswordAuthScreenProps = {
  errorMessage: string;
  infoMessage?: string;
  isPasswordVisible: boolean;
  isSubmitting: boolean;
  onBack: () => void;
  onChangePassword: (value: string) => void;
  onContinue: () => void;
  onForgotPassword: () => void;
  onToggleRememberMe: () => void;
  onTogglePassword: () => void;
  password: string;
  rememberMe: boolean;
};

export function PasswordAuthScreen({
  errorMessage,
  infoMessage,
  isPasswordVisible,
  isSubmitting,
  onBack,
  onChangePassword,
  onContinue,
  onForgotPassword,
  onToggleRememberMe,
  onTogglePassword,
  password,
  rememberMe,
}: PasswordAuthScreenProps) {
  return (
    <View style={styles.passwordScreen}>
      <ScrollView
        contentContainerStyle={styles.passwordContent}
        keyboardShouldPersistTaps="handled"
        style={styles.passwordScroll}
      >
        <BackButton onPress={onBack} />
        <AuthGradientText
          fontSize={39}
          fontFamily="Poppins-SemiBold"
          height={76}
          lineHeight={35}
          text={"Bem-Vindo\nde volta!"}
          width={300}
          y={32}
        />
        <Text style={styles.bodyText}>
          Nós achamos uma conta vinculada a este e-mail. Por favor, insira sua
          senha.
        </Text>

        <PaperAuthInput
          testID="auth-password"
          label="Senha"
          onChangeText={onChangePassword}
          onToggleVisibility={onTogglePassword}
          passwordVisible={isPasswordVisible}
          secureTextEntry={!isPasswordVisible}
          value={password}
        />

        {infoMessage ? (
          <Text style={styles.bodyText}>{infoMessage}</Text>
        ) : null}
        {errorMessage ? (
          <Text style={styles.errorText}>{errorMessage}</Text>
        ) : null}

        <View style={styles.optionsRow}>
          <Pressable onPress={onToggleRememberMe} style={styles.rememberRow}>
            <View
              style={[styles.checkbox, rememberMe && styles.checkboxChecked]}
            >
              {rememberMe ? <Text style={styles.checkmark}>✓</Text> : null}
            </View>
            <Text style={styles.rememberText}>Lembrar de mim</Text>
          </Pressable>

          <Pressable onPress={onForgotPassword} style={styles.resetInline}>
            <Text style={styles.resetText}>REDEFINIR SENHA</Text>
          </Pressable>
        </View>
      </ScrollView>

      <View style={styles.passwordFooter}>
        <GradientButton
          disabled={isSubmitting}
          label={isSubmitting ? "ENTRANDO..." : "CONTINUE"}
          onPress={onContinue}
        />
      </View>
    </View>
  );
}
