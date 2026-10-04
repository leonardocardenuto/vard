import { ScrollView, Text } from "react-native";

import { AuthGradientText } from "../components/AuthGradientText";
import { BackButton } from "../components/BackButton";
import { GradientButton } from "../components/GradientButton";
import { PaperAuthInput } from "../components/PaperAuthInput";
import { styles } from "../auth_screen";

type ForgotPasswordScreenProps = {
  email: string;
  errorMessage: string;
  isSubmitting: boolean;
  onBack: () => void;
  onChangeEmail: (value: string) => void;
  onContinue: () => void;
};

export function ForgotPasswordScreen({
  email,
  errorMessage,
  isSubmitting,
  onBack,
  onChangeEmail,
  onContinue,
}: ForgotPasswordScreenProps) {
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
        text={"Esqueceu\na senha?"}
        width={300}
        y={32}
      />
      <Text style={styles.bodyText}>
        Confirme seu email e enviaremos um codigo para voce criar uma nova
        senha.
      </Text>

      <PaperAuthInput
        autoCapitalize="none"
        keyboardType="email-address"
        label="Email"
        onChangeText={onChangeEmail}
        value={email}
      />

      {errorMessage ? (
        <Text style={styles.errorText}>{errorMessage}</Text>
      ) : null}

      <GradientButton
        disabled={isSubmitting}
        label={isSubmitting ? "ENVIANDO..." : "ENVIAR CODIGO"}
        onPress={onContinue}
      />
    </ScrollView>
  );
}
