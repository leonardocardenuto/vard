import { useEffect, useState } from 'react';
import { useNavigation } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { StatusBar } from 'expo-status-bar';
import {
  Animated,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import VardHorizontalLogo from '../../../../assets/vard_logo_horizontal.svg';
import { ApiRequestError, getMe, login, register } from '../../../lib/api';
import { RootStackParamList } from '../../../navigation/types';
import { AuthForm } from '../components/AuthForm';
import { AuthModeToggle } from '../components/AuthModeToggle';
import { AuthSubmitButton } from '../components/AuthSubmitButton';
import {
  AuthFormErrors,
  AuthFormState,
  AuthMode,
  initialAuthFormState,
} from '../types/auth';
import { formatPhone } from '../utils/formatPhone';

export function AuthScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const [mode, setMode] = useState<AuthMode>('signup');
  const [form, setForm] = useState<AuthFormState>(initialAuthFormState);
  const [fieldErrors, setFieldErrors] = useState<AuthFormErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const [isPasswordVisible, setIsPasswordVisible] = useState(false);
  const toggleOffset = useState(new Animated.Value(1))[0];

  useEffect(() => {
    Animated.spring(toggleOffset, {
      toValue: mode === 'login' ? 0 : 1,
      useNativeDriver: true,
      damping: 20,
      mass: 1,
      stiffness: 125,
    }).start();
  }, [mode, toggleOffset]);

  useEffect(() => {
    setFieldErrors({});
    setSuccessMessage('');
    setIsPasswordVisible(false);
  }, [mode]);

  useEffect(() => {
    if (!successMessage) {
      return;
    }

    const timeout = setTimeout(() => {
      setSuccessMessage('');
    }, 3200);

    return () => clearTimeout(timeout);
  }, [successMessage]);

  function updateField(field: keyof AuthFormState, value: string) {
    const nextValue = field === 'phone' ? formatPhone(value) : value;

    setForm((current) => ({
      ...current,
      [field]: nextValue,
    }));
    setFieldErrors((current) => {
      if (!current[field]) {
        return current;
      }

      return {
        ...current,
        [field]: undefined,
      };
    });
  }

  async function handleSubmit() {
    const email = form.email.trim().toLowerCase();
    const password = form.password.trim();
    const fullName = form.fullName.trim();
    const phone = form.phone.trim();

    const nextFieldErrors: AuthFormErrors = {};

    if (!email) {
      nextFieldErrors.email = 'Preencha seu e-mail.';
    }

    if (!password) {
      nextFieldErrors.password = 'Preencha sua senha.';
    }

    if (mode === 'signup' && !fullName) {
      nextFieldErrors.fullName = 'Preencha seu nome completo.';
    }

    if (Object.keys(nextFieldErrors).length > 0) {
      setFieldErrors(nextFieldErrors);
      setSuccessMessage('');
      return;
    }

    setIsSubmitting(true);
    setFieldErrors({});
    setSuccessMessage('');

    try {
      const authResponse =
        mode === 'signup'
          ? await register({
              email,
              password,
              full_name: fullName,
              phone: phone || undefined,
            })
          : await login({
              email,
              password,
            });

      const me = await getMe(authResponse.access_token);
      const resolvedName = me.full_name?.trim() || me.email;

      setSuccessMessage(
        mode === 'signup'
          ? `Conta criada com sucesso. Bem-vindo, ${resolvedName}.`
          : `Login realizado com sucesso. Bem-vindo de volta, ${resolvedName}.`
      );

      navigation.reset({
        index: 0,
        routes: [
          {
            name: 'AppTabs',
            params: {
              accessToken: authResponse.access_token,
              userEmail: me.email,
              userName: resolvedName,
            },
          },
        ],
      });

      if (mode === 'login') {
        setForm((current) => ({
          ...current,
          password: '',
        }));
      }
    } catch (error) {
      if (error instanceof ApiRequestError) {
        const apiFieldErrors: AuthFormErrors = {};

        if (error.fieldErrors?.email) {
          apiFieldErrors.email = error.fieldErrors.email;
        }

        if (error.fieldErrors?.password) {
          apiFieldErrors.password = error.fieldErrors.password;
        }

        if (error.fieldErrors?.full_name) {
          apiFieldErrors.fullName = error.fieldErrors.full_name;
        }

        if (error.fieldErrors?.phone) {
          apiFieldErrors.phone = error.fieldErrors.phone;
        }

        if (Object.keys(apiFieldErrors).length > 0) {
          setFieldErrors(apiFieldErrors);
        } else {
          setFieldErrors({
            password: error.message,
          });
        }
      } else {
        setFieldErrors({
          password: 'Não foi possível conectar com a API.',
        });
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  const isSignup = mode === 'signup';

  return (
    <View style={styles.screen}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.keyboardArea}
      >
        <ScrollView
          bounces={false}
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.brandWrap}>
            <VardHorizontalLogo width={160} height={42} />
          </View>

          <AuthModeToggle mode={mode} onChangeMode={setMode} toggleOffset={toggleOffset} />

          <View style={styles.heroBlock}>
            <Text style={styles.title}>
              {isSignup ? 'Entre para o círculo' : 'Bem-vindo de volta'}
            </Text>
            <Text style={styles.subtitle}>
              {isSignup
                ? 'Comece sua jornada para cuidar melhor da sua família.'
                : 'Acesse sua conta para acompanhar câmeras, alertas e seu workspace.'}
            </Text>
          </View>

          <AuthForm
            fieldErrors={fieldErrors}
            form={form}
            isPasswordVisible={isPasswordVisible}
            mode={mode}
            onTogglePasswordVisibility={() => setIsPasswordVisible((current) => !current)}
            onUpdateField={updateField}
          />

          <AuthSubmitButton
            isSubmitting={isSubmitting}
            mode={mode}
            onPress={handleSubmit}
            successMessage={successMessage}
          />

          <Text style={styles.footerText}>
            {isSignup
              ? 'Ao continuar, você concorda com os Termos de Serviço e a Política de Privacidade.'
              : 'Ao entrar, você concorda com os Termos de Serviço e a Política de Privacidade.'}
          </Text>
        </ScrollView>
      </KeyboardAvoidingView>
      <StatusBar style="dark" />
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: '#FBF5EC',
  },
  keyboardArea: {
    flex: 1,
  },
  content: {
    paddingHorizontal: 26,
    paddingTop: 30,
    paddingBottom: 18,
  },
  brandWrap: {
    alignItems: 'center',
    marginBottom: 12,
  },
  heroBlock: {
    marginBottom: 14,
    gap: 4,
  },
  title: {
    color: '#302611',
    fontSize: 23,
    lineHeight: 27,
    fontWeight: '800',
    letterSpacing: -1.2,
  },
  subtitle: {
    color: '#786E58',
    fontSize: 14,
    lineHeight: 20,
    maxWidth: 278,
  },
  footerText: {
    color: '#726951',
    fontSize: 12,
    lineHeight: 16,
    textAlign: 'center',
    marginTop: 10,
    paddingHorizontal: 8,
  },
});
