import { useEffect, useState } from 'react';
import { LinearGradient } from 'expo-linear-gradient';
import { StatusBar } from 'expo-status-bar';
import {
  Animated,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import Feather from 'expo/node_modules/@expo/vector-icons/Feather';

import VardLogo from './assets/vard_logo.svg';
import VardHorizontalLogo from './assets/vard_logo_horizontal.svg';
import { OrbitDotLoader } from './src/components/OrbitDotLoader';
import { ApiRequestError, getMe, login, register } from './src/lib/api';

type AuthMode = 'login' | 'signup';

type FormState = {
  fullName: string;
  email: string;
  phone: string;
  password: string;
};

type FormErrors = Partial<Record<keyof FormState, string>>;

const initialFormState: FormState = {
  fullName: '',
  email: '',
  phone: '',
  password: '',
};

export default function App() {
  const [isSplashVisible, setIsSplashVisible] = useState(true);
  const [mode, setMode] = useState<AuthMode>('signup');
  const [form, setForm] = useState<FormState>(initialFormState);
  const [fieldErrors, setFieldErrors] = useState<FormErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const [userName, setUserName] = useState('');
  const [isPasswordVisible, setIsPasswordVisible] = useState(false);
  const toggleOffset = useState(new Animated.Value(1))[0];

  useEffect(() => {
    const timeout = setTimeout(() => {
      setIsSplashVisible(false);
    }, 1600);

    return () => clearTimeout(timeout);
  }, []);

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
    setUserName('');
    setIsPasswordVisible(false);
  }, [mode]);

  useEffect(() => {
    if (!successMessage) {
      return;
    }

    const timeout = setTimeout(() => {
      setSuccessMessage('');
      setUserName('');
    }, 3200);

    return () => clearTimeout(timeout);
  }, [successMessage]);

  function updateField(field: keyof FormState, value: string) {
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

    const nextFieldErrors: FormErrors = {};

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

      setUserName(resolvedName);
      setSuccessMessage(
        mode === 'signup'
          ? `Conta criada com sucesso. Bem-vindo, ${resolvedName}.`
          : `Login realizado com sucesso. Bem-vindo de volta, ${resolvedName}.`
      );

      if (mode === 'login') {
        setForm((current) => ({
          ...current,
          password: '',
        }));
      }
    } catch (error) {
      if (error instanceof ApiRequestError) {
        const apiFieldErrors: FormErrors = {};

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

  if (isSplashVisible) {
    return (
      <LinearGradient
        colors={['#03CDF4', '#019BDE', '#01EBD0']}
        locations={[0.01, 0.48, 1]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.splashContainer}
      >
        <View style={styles.splashContent}>
          <VardLogo width={170} height={251} />
        </View>
        <StatusBar style="light" />
      </LinearGradient>
    );
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

          <View style={styles.toggle}>
            <Animated.View
              pointerEvents="none"
              style={[
                styles.toggleHighlight,
                {
                  transform: [
                    {
                      translateX: toggleOffset.interpolate({
                        inputRange: [0, 1],
                        outputRange: [0, 102],
                      }),
                    },
                  ],
                },
              ]}
            />
            <Pressable onPress={() => setMode('login')} style={styles.toggleButton}>
              <Text style={[styles.toggleLabel, mode === 'login' && styles.toggleLabelActive]}>
                Entrar
              </Text>
            </Pressable>
            <Pressable onPress={() => setMode('signup')} style={styles.toggleButton}>
              <Text style={[styles.toggleLabel, mode === 'signup' && styles.toggleLabelActive]}>
                Criar conta
              </Text>
            </Pressable>
          </View>

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

          <View style={styles.form}>
            {isSignup ? (
              <>
                <Field
                  error={fieldErrors.fullName}
                  label="Nome completo"
                  onChangeText={(value) => updateField('fullName', value)}
                  placeholder="Ex.: Evelyn Harper"
                  value={form.fullName}
                />
                <Field
                  autoCapitalize="none"
                  error={fieldErrors.email}
                  keyboardType="email-address"
                  label="Endereço de e-mail"
                  onChangeText={(value) => updateField('email', value)}
                  placeholder="você@familia.com"
                  value={form.email}
                />
                <Field
                  error={fieldErrors.phone}
                  keyboardType="phone-pad"
                  label="Telefone"
                  onChangeText={(value) => updateField('phone', value)}
                  placeholder="(11) 99999-0000"
                  value={form.phone}
                />
                <Field
                  error={fieldErrors.password}
                  label="Senha"
                  onChangeText={(value) => updateField('password', value)}
                  placeholder="Crie uma senha segura"
                  onTogglePasswordVisibility={() => setIsPasswordVisible((current) => !current)}
                  passwordVisible={isPasswordVisible}
                  secureTextEntry={!isPasswordVisible}
                  showPasswordToggle
                  value={form.password}
                />
              </>
            ) : (
              <>
                <Field
                  autoCapitalize="none"
                  error={fieldErrors.email}
                  keyboardType="email-address"
                  label="Endereço de e-mail"
                  onChangeText={(value) => updateField('email', value)}
                  placeholder="você@familia.com"
                  value={form.email}
                />
                <Field
                  error={fieldErrors.password}
                  label="Senha"
                  onChangeText={(value) => updateField('password', value)}
                  placeholder="Sua senha"
                  onTogglePasswordVisibility={() => setIsPasswordVisible((current) => !current)}
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

          <Pressable
            disabled={isSubmitting}
            onPress={handleSubmit}
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

type FieldProps = {
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

function Field({
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
}: FieldProps) {
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

function formatPhone(value: string) {
  const digits = value.replace(/\D/g, '').slice(0, 11);

  if (!digits) {
    return '';
  }

  if (digits.length <= 2) {
    return `(${digits}`;
  }

  if (digits.length <= 6) {
    return `(${digits.slice(0, 2)}) ${digits.slice(2)}`;
  }

  if (digits.length <= 10) {
    return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`;
  }

  return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`;
}

const styles = StyleSheet.create({
  splashContainer: {
    flex: 1,
  },
  splashContent: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
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
  toggle: {
    position: 'relative',
    flexDirection: 'row',
    alignSelf: 'center',
    backgroundColor: '#F3E8D3',
    borderRadius: 16,
    padding: 4,
    marginBottom: 14,
  },
  toggleHighlight: {
    position: 'absolute',
    top: 4,
    left: 4,
    width: 102,
    bottom: 4,
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    shadowColor: '#8A7750',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.08,
    shadowRadius: 16,
    elevation: 2,
  },
  toggleButton: {
    minWidth: 102,
    paddingVertical: 7,
    paddingHorizontal: 12,
    borderRadius: 12,
    alignItems: 'center',
    zIndex: 1,
  },
  toggleLabel: {
    color: '#7F745F',
    fontSize: 14,
    fontWeight: '700',
  },
  toggleLabelActive: {
    color: '#302611',
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
  form: {
    gap: 12,
  },
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
  inlineAction: {
    alignSelf: 'flex-end',
    marginTop: -4,
  },
  inlineActionText: {
    color: '#2E86BD',
    fontSize: 13,
    fontWeight: '700',
  },
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
  footerText: {
    color: '#726951',
    fontSize: 12,
    lineHeight: 16,
    textAlign: 'center',
    marginTop: 10,
    paddingHorizontal: 8,
  },
});
