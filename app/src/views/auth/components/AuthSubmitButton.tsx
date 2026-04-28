import { Pressable, StyleSheet, Text, View } from 'react-native';

import { OrbitDotLoader } from '../../../components/OrbitDotLoader';
import { AuthMode } from '../types/auth';

type AuthSubmitButtonProps = {
  isSubmitting: boolean;
  mode: AuthMode;
  onPress: () => void;
  successMessage: string;
};

export function AuthSubmitButton({
  isSubmitting,
  mode,
  onPress,
  successMessage,
}: AuthSubmitButtonProps) {
  const isSignup = mode === 'signup';

  return (
    <Pressable
      disabled={isSubmitting}
      onPress={onPress}
      style={[
        styles.primaryButton,
        isSubmitting && styles.primaryButtonDisabled,
        successMessage && styles.primaryButtonSuccess,
      ]}
    >
      {isSubmitting ? (
        <View style={styles.loaderWrap}>
          <OrbitDotLoader dotColor="#FFFFFF" dotRadius={3} centerRadius={4} numDots={3} size={24} />
          <Text style={styles.primaryButtonText}>
            {isSignup ? 'Criando conta' : 'Entrando'}
          </Text>
        </View>
      ) : (
        <>
          <Text style={styles.primaryButtonText}>
            {successMessage ? 'Tudo certo' : isSignup ? 'Criar conta' : 'Entrar'}
          </Text>
          <Text style={styles.primaryButtonArrow}>{'>'}</Text>
        </>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  primaryButton: {
    minHeight: 52,
    borderRadius: 20,
    backgroundColor: '#1979B6',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    marginTop: 16,
    shadowColor: '#1C6EA4',
    shadowOffset: { width: 0, height: 16 },
    shadowOpacity: 0.24,
    shadowRadius: 26,
    elevation: 8,
    marginBottom: 10,
  },
  primaryButtonDisabled: {
    opacity: 0.92,
  },
  primaryButtonSuccess: {
    backgroundColor: '#3F8E5A',
  },
  loaderWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  primaryButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '800',
  },
  primaryButtonArrow: {
    color: '#FFFFFF',
    fontSize: 22,
    lineHeight: 24,
    marginTop: -2,
  },
});
