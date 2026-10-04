import { Pressable, ScrollView, Text } from "react-native";

import { AuthGradientText } from "../components/AuthGradientText";
import { BackButton } from "../components/BackButton";
import { GradientButton } from "../components/GradientButton";
import { PaperAuthInput } from "../components/PaperAuthInput";
import { styles } from "../auth_screen";

type ResetPasswordScreenProps = {
  code: string;
  confirmPassword: string;
  email: string;
  errorMessage: string;
  infoMessage: string;
  isPasswordVisible: boolean;
  isSubmitting: boolean;
  newPassword: string;
  onBack: () => void;
  onChangeCode: (value: string) => void;
  onChangeConfirmPassword: (value: string) => void;
  onChangeNewPassword: (value: string) => void;
  onConfirm: () => void;
  onResend: () => void;
  onTogglePassword: () => void;
};

export function ResetPasswordScreen({
  code,
  confirmPassword,
  email,
  errorMessage,
  infoMessage,
  isPasswordVisible,
  isSubmitting,
  newPassword,
  onBack,
  onChangeCode,
  onChangeConfirmPassword,
  onChangeNewPassword,
  onConfirm,
  onResend,
  onTogglePassword,
}: ResetPasswordScreenProps) {
  return (
    <ScrollView
      contentContainerStyle={styles.passwordContent}
      keyboardShouldPersistTaps="handled"
    >
      <BackButton onPress={onBack} />
      <AuthGradientText
        fontSize={34}
        fontFamily="Poppins-SemiBold"
        height={76}
        lineHeight={35}
        text={"Crie uma\nnova senha"}
        width={300}
        y={32}
      />
      <Text style={styles.bodyText}>
        Enviamos um codigo de 6 digitos para {email}.
      </Text>

      <PaperAuthInput
        keyboardType="number-pad"
        label="Codigo"
        maxLength={6}
        onChangeText={(value: string) => onChangeCode(value.replace(/\D/g, ""))}
        value={code}
      />
      <PaperAuthInput
        label="Nova senha"
        onChangeText={onChangeNewPassword}
        onToggleVisibility={onTogglePassword}
        passwordVisible={isPasswordVisible}
        secureTextEntry={!isPasswordVisible}
        value={newPassword}
      />
      <PaperAuthInput
        label="Confirmar nova senha"
        onChangeText={onChangeConfirmPassword}
        onToggleVisibility={onTogglePassword}
        passwordVisible={isPasswordVisible}
        secureTextEntry={!isPasswordVisible}
        value={confirmPassword}
      />

      {infoMessage ? <Text style={styles.bodyText}>{infoMessage}</Text> : null}
      {errorMessage ? (
        <Text style={styles.errorText}>{errorMessage}</Text>
      ) : null}

      <GradientButton
        disabled={isSubmitting}
        label={isSubmitting ? "SALVANDO..." : "REDEFINIR SENHA"}
        onPress={onConfirm}
      />

      <Pressable
        disabled={isSubmitting}
        onPress={onResend}
        style={styles.resetButton}
      >
        <Text style={styles.resetText}>REENVIAR CODIGO</Text>
      </Pressable>
    </ScrollView>
  );
}
