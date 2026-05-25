import { useNavigation } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useFonts } from 'expo-font';
import * as ImagePicker from 'expo-image-picker';
import { StatusBar } from 'expo-status-bar';
import { useMemo, useState } from 'react';
import { Alert, KeyboardAvoidingView, Platform, View } from 'react-native';
import { pt, registerTranslation } from 'react-native-paper-dates';
import {
  ApiRequestError,
  checkEmail,
  getMe,
  login,
  register,
} from '../../../lib/api';
import { RootStackParamList } from '../../../navigation/types';
import { EmailAuthScreen } from '../screens/EmailAuthScreen';
import { LandingAuthScreen } from '../screens/LandingAuthScreen';
import { PasswordAuthScreen } from '../screens/PasswordAuthScreen';
import { SignupAuthScreen } from '../screens/SignupAuthScreen';
import { AuthStep, SignupForm, initialSignupForm } from '../types/flow';
import { styles } from '../auth_screen';

registerTranslation('pt', pt);

export function AuthScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const [fontsLoaded] = useFonts({
    'Poppins-Regular': require('../../../../assets/fonts/Poppins-Regular.ttf'),
    'Poppins-Medium': require('../../../../assets/fonts/Poppins-Medium.ttf'),
    'Poppins-SemiBold': require('../../../../assets/fonts/Poppins-SemiBold.ttf'),
    'Poppins-ExtraBold': require('../../../../assets/fonts/Poppins-ExtraBold.ttf'),
  });
  const [step, setStep] = useState<AuthStep>('landing');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isPasswordVisible, setIsPasswordVisible] = useState(false);
  const [signupForm, setSignupForm] = useState<SignupForm>(initialSignupForm);
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [isBirthDatePickerOpen, setIsBirthDatePickerOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const normalizedEmail = email.trim().toLowerCase();
  const fullName = useMemo(
    () => `${signupForm.firstName.trim()} ${signupForm.lastName.trim()}`.trim(),
    [signupForm.firstName, signupForm.lastName]
  );

  if (!fontsLoaded) {
    return null;
  }

  function updateSignupField(field: keyof SignupForm, value: string) {
    setSignupForm((current) => ({ ...current, [field]: value }));
    setErrorMessage('');
  }

  function goBack() {
    setErrorMessage('');
    if (step === 'landing') {
      return;
    }
    if (step === 'email') {
      setStep('landing');
      return;
    }
    setStep('email');
  }

  async function handleEmailContinue() {
    if (!normalizedEmail) {
      setErrorMessage('Informe seu endereco de email.');
      return;
    }

    setIsSubmitting(true);
    setErrorMessage('');

    try {
      const response = await checkEmail(normalizedEmail);
      if (response.exists) {
        setStep('password');
      } else {
        goToSignupFromEmail();
      }
    } catch (error) {
      if (error instanceof ApiRequestError && error.message === 'Not Found') {
        setErrorMessage('Nao foi possivel verificar esse email. Atualize a API e tente novamente.');
      } else {
        setErrorMessage(error instanceof Error ? error.message : 'Nao foi possivel verificar seu email.');
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  function goToSignupFromEmail() {
    setSignupForm((current) => ({
      ...current,
      firstName: current.firstName || nameFromEmail(normalizedEmail),
    }));
    setStep('signup');
  }

  async function finishAuth(accessToken: string, fallbackAvatarUrl?: string) {
    const me = await getMe(accessToken);
    const resolvedName = me.full_name?.trim() || me.email;
    const resolvedAvatarUrl = me.avatar_url || fallbackAvatarUrl || null;

    navigation.reset({
      index: 0,
      routes: [
        {
          name: 'AppTabs',
          params: {
            accessToken,
            userEmail: me.email,
            userAvatarUrl: resolvedAvatarUrl,
            userName: resolvedName,
          },
        },
      ],
    });
  }

  async function handleLogin() {
    if (!password.trim()) {
      setErrorMessage('Informe sua senha.');
      return;
    }

    setIsSubmitting(true);
    setErrorMessage('');

    try {
      const response = await login({ email: normalizedEmail, password: password.trim() });
      await finishAuth(response.access_token);
    } catch (error) {
      setErrorMessage(error instanceof ApiRequestError ? error.message : 'Nao foi possivel entrar.');
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCreateAccount() {
    if (!fullName) {
      setErrorMessage('Informe seu nome e sobrenome.');
      return;
    }
    if (signupForm.password.length < 8) {
      setErrorMessage('A senha precisa ter pelo menos 8 caracteres.');
      return;
    }
    if (signupForm.password !== signupForm.confirmPassword) {
      setErrorMessage('As senhas nao conferem.');
      return;
    }
    if (!acceptedTerms) {
      setErrorMessage('Aceite os termos para criar sua conta.');
      return;
    }

    setIsSubmitting(true);
    setErrorMessage('');

    try {
      const response = await register({
        email: normalizedEmail,
        password: signupForm.password,
        avatar_url: signupForm.avatarUrl || undefined,
        birth_date: signupForm.birthDateIso || undefined,
        full_name: fullName,
      });
      await finishAuth(response.access_token, signupForm.avatarUrl);
    } catch (error) {
      if (error instanceof ApiRequestError && error.message.includes('cadastrado')) {
        setErrorMessage('Esse email ja esta cadastrado. Volte e entre com sua senha.');
      } else {
        setErrorMessage(error instanceof Error ? error.message : 'Nao foi possivel criar sua conta.');
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handlePickAvatar() {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();

    if (!permission.granted) {
      Alert.alert('Permissao necessaria', 'Permita acesso as suas fotos para escolher uma imagem de perfil.');
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      allowsEditing: true,
      aspect: [1, 1],
      base64: true,
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.72,
    });

    if (result.canceled || !result.assets[0]) {
      return;
    }

    const asset = result.assets[0];
    const avatarUrl = asset.base64
      ? `data:${asset.mimeType ?? 'image/jpeg'};base64,${asset.base64}`
      : asset.uri;

    updateSignupField('avatarUrl', avatarUrl);
  }

  function handleSelectBirthDate(date: Date) {
    updateSignupField('birthDateIso', formatDateIso(date));
    updateSignupField('birthDate', formatDatePtBr(date));
    setIsBirthDatePickerOpen(false);
  }

  return (
    <View style={styles.screen}>
      <StatusBar style="dark" />
      {step === 'landing' ? (
        <LandingAuthScreen onAccessAccount={() => setStep('email')} />
      ) : (
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          style={styles.keyboardArea}
        >
          {step === 'email' ? (
            <EmailAuthScreen
              email={email}
              errorMessage={errorMessage}
              isSubmitting={isSubmitting}
              onChangeEmail={(value) => {
                setEmail(value);
                setErrorMessage('');
              }}
              onContinue={handleEmailContinue}
            />
          ) : step === 'password' ? (
            <PasswordAuthScreen
              errorMessage={errorMessage}
              isPasswordVisible={isPasswordVisible}
              isSubmitting={isSubmitting}
              onBack={goBack}
              onChangePassword={(value) => {
                setPassword(value);
                setErrorMessage('');
              }}
              onContinue={handleLogin}
              onTogglePassword={() => setIsPasswordVisible((current) => !current)}
              password={password}
            />
          ) : (
            <SignupAuthScreen
              acceptedTerms={acceptedTerms}
              errorMessage={errorMessage}
              form={signupForm}
              isPasswordVisible={isPasswordVisible}
              isSubmitting={isSubmitting}
              onBack={goBack}
              onChangeField={updateSignupField}
              onCreateAccount={handleCreateAccount}
              onDismissBirthDatePicker={() => setIsBirthDatePickerOpen(false)}
              onOpenBirthDatePicker={() => setIsBirthDatePickerOpen(true)}
              onPickAvatar={handlePickAvatar}
              onSelectBirthDate={handleSelectBirthDate}
              onTogglePassword={() => setIsPasswordVisible((current) => !current)}
              onToggleTerms={() => {
                setAcceptedTerms((current) => !current);
                setErrorMessage('');
              }}
              isBirthDatePickerOpen={isBirthDatePickerOpen}
            />
          )}
        </KeyboardAvoidingView>
      )}
    </View>
  );
}


function formatDateIso(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function formatDatePtBr(date: Date) {
  const day = String(date.getDate()).padStart(2, '0');
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const year = date.getFullYear();
  return `${day}/${month}/${year}`;
}

function nameFromEmail(value: string) {
  const localPart = value.split('@')[0] || '';
  const firstToken = localPart.split(/[._-]/)[0] || '';
  return firstToken ? firstToken.charAt(0).toUpperCase() + firstToken.slice(1) : '';
}
