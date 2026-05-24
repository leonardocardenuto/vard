import { ScrollView, Text, View } from 'react-native';

import { AuthGradientText } from '../components/AuthGradientText';
import { GradientButton } from '../components/GradientButton';
import { PaperAuthInput } from '../components/PaperAuthInput';
import { TermsText } from '../components/TermsText';
import { styles } from '../auth_screen';

type EmailAuthScreenProps = {
  email: string;
  errorMessage: string;
  isSubmitting: boolean;
  onChangeEmail: (value: string) => void;
  onContinue: () => void;
};

export function EmailAuthScreen({
  email,
  errorMessage,
  isSubmitting,
  onChangeEmail,
  onContinue,
}: EmailAuthScreenProps) {
  return (
    <ScrollView
      contentContainerStyle={styles.formContent}
      keyboardShouldPersistTaps="handled"
      showsVerticalScrollIndicator={false}
    >
      <View style={styles.topLabelGradient}>
        <AuthGradientText
          fontFamily="Poppins-Regular"
          fontSize={14}
          height={20}
          text="Bem-Vindo"
          textAnchor="middle"
          width={120}
          y={15}
        />
      </View>
      <View style={styles.bigTitleGradient}>
        <AuthGradientText
          fontFamily="Poppins-SemiBold"
          fontSize={34}
          height={76}
          lineHeight={35}
          text={'Entre ou crie\nsua conta'}
          width={300}
          y={32}
        />
      </View>
      <Text style={styles.bodyText}>Monitore a saude de seus familiares por aqui dlsald sldslsada sldalsdlsadlsa!</Text>

      <PaperAuthInput
        autoCapitalize="none"
        keyboardType="email-address"
        label="Endereco de email"
        onChangeText={onChangeEmail}
        onClear={() => onChangeEmail('')}
        value={email}
      />

      {errorMessage ? <Text style={styles.errorText}>{errorMessage}</Text> : null}

      <GradientButton disabled={isSubmitting} label={isSubmitting ? 'VERIFICANDO...' : 'CONTINUE'} onPress={onContinue} />

      <View style={styles.emailSpacer} />
      <Text style={styles.orText}>or continue with</Text>
      <View style={styles.googleButton}>
        <Text style={styles.googleIcon}>G</Text>
        <Text style={styles.googleText}>Continue with Google</Text>
      </View>

      <TermsText />
    </ScrollView>
  );
}
