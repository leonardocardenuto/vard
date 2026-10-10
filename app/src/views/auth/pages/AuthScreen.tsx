import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useFonts } from 'expo-font';
import * as ImagePicker from 'expo-image-picker';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useMemo, useState } from 'react';
import { Alert, KeyboardAvoidingView, Platform, View } from 'react-native';
import { pt, registerTranslation } from 'react-native-paper-dates';
import { SafeAreaView } from 'react-native-safe-area-context';
import {
  ApiRequestError,
  checkEmail,
  confirmPasswordReset,
  getMe,
  login,
  register,
  requestPasswordReset,
  updateMyOneSignalSubscription,
} from '../../../lib/api';
import { prepareFallHistoryKey } from '../../../lib/fallHistoryCrypto';
import { identifyOneSignalUser } from '../../../lib/onesignal';
import { clearSession, loadToken, saveToken } from '../../../lib/session';
import { RootStackParamList } from '../../../navigation/types';
import { EmailAuthScreen } from '../screens/EmailAuthScreen';
import { ForgotPasswordScreen } from '../screens/ForgotPasswordScreen';
import { LandingAuthScreen } from '../screens/LandingAuthScreen';
import { PasswordAuthScreen } from '../screens/PasswordAuthScreen';
import { ResetPasswordScreen } from '../screens/ResetPasswordScreen';
import { SignupAuthScreen } from '../screens/SignupAuthScreen';
import { AuthStep, SignupForm, initialSignupForm } from '../types/flow';
import { styles } from '../auth_screen';

registerTranslation("pt", pt);

type Props = NativeStackScreenProps<RootStackParamList, 'Auth'>;

export function AuthScreen({ navigation, route }: Props) {
  const [fontsLoaded] = useFonts({
    "Poppins-Regular": require("../../../../assets/fonts/Poppins-Regular.ttf"),
    "Poppins-Medium": require("../../../../assets/fonts/Poppins-Medium.ttf"),
    "Poppins-SemiBold": require("../../../../assets/fonts/Poppins-SemiBold.ttf"),
    "Poppins-ExtraBold": require("../../../../assets/fonts/Poppins-ExtraBold.ttf"),
  });
  const [step, setStep] = useState<AuthStep>(route.params?.initialStep ?? 'landing');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isPasswordVisible, setIsPasswordVisible] = useState(false);
  const [signupForm, setSignupForm] = useState<SignupForm>(initialSignupForm);
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [isBirthDatePickerOpen, setIsBirthDatePickerOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [infoMessage, setInfoMessage] = useState("");
  const [resetCode, setResetCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(true);
  const [isRestoring, setIsRestoring] = useState(true);

  const normalizedEmail = email.trim().toLowerCase();
  const fullName = useMemo(
    () => `${signupForm.firstName.trim()} ${signupForm.lastName.trim()}`.trim(),
    [signupForm.firstName, signupForm.lastName],
  );

  useEffect(() => {
    let active = true;

    async function restoreSession() {
      try {
        const token = await loadToken();
        if (token) {
          await finishAuth(token);
          return;
        }
      } catch {
        await clearSession();
      } finally {
        if (active) {
          setIsRestoring(false);
        }
      }
    }

    restoreSession();

    return () => {
      active = false;
    };
  }, []);

  if (!fontsLoaded || isRestoring) {
    return null;
  }

  function updateSignupField(field: keyof SignupForm, value: string) {
    setSignupForm((current) => ({ ...current, [field]: value }));
    setErrorMessage("");
  }

  function goBack() {
    setErrorMessage("");
    setInfoMessage("");
    if (step === "landing") {
      return;
    }
    if (step === "email") {
      setStep("landing");
      return;
    }
    if (step === "reset") {
      setStep("forgot");
      return;
    }
    if (step === "forgot") {
      setStep("password");
      return;
    }
    setStep("email");
  }

  async function handleEmailContinue() {
    if (!normalizedEmail) {
      setErrorMessage('Informe seu endereço de e-mail.');
      return;
    }

    setIsSubmitting(true);
    setErrorMessage("");

    try {
      const response = await checkEmail(normalizedEmail);
      if (response.exists) {
        setStep("password");
      } else {
        goToSignupFromEmail();
      }
    } catch (error) {
      if (error instanceof ApiRequestError && error.message === 'Not Found') {
        setErrorMessage('Não foi possível verificar esse e-mail. Atualize a API e tente novamente.');
      } else {
        setErrorMessage(error instanceof Error ? error.message : 'Não foi possível verificar seu e-mail.');
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
    setStep("signup");
  }

  async function finishAuth(
    accessToken: string,
    fallbackAvatarUrl?: string,
    passwordForRecovery?: string,
    persist = false,
  ) {
    const me = await getMe(accessToken);
    if (passwordForRecovery) {
      try {
        // The camera history is decrypted locally. Wait until this device has
        // restored its private key before opening the live camera screen.
        await prepareFallHistoryKey(accessToken, me.id, passwordForRecovery);
      } catch (error) {
        console.warn('Não foi possível preparar a chave do histórico de quedas.', error);
      }
    }
    if (persist) {
      await saveToken(accessToken);
    }
    await syncOneSignalSubscription(accessToken, me.id);

    const resolvedName = me.full_name?.trim() || me.email;
    const resolvedAvatarUrl = me.avatar_url || fallbackAvatarUrl || null;

    const appTabsRoute = {
      name: 'AppTabs' as const,
      params: {
        accessToken,
        userEmail: me.email,
        userAvatarUrl: resolvedAvatarUrl,
        userName: resolvedName,
      },
    };
    const pendingInviteToken = route.params?.pendingInviteToken;
    navigation.reset(
      pendingInviteToken
        ? {
            index: 1,
            routes: [appTabsRoute, { name: 'AcceptInvite', params: { token: pendingInviteToken } }],
          }
        : { index: 0, routes: [appTabsRoute] }
    );
  }

  async function syncOneSignalSubscription(
    accessToken: string,
    userId: string,
  ) {
    try {
      const subscriptionId = await identifyOneSignalUser(userId);
      if (subscriptionId) {
        await updateMyOneSignalSubscription(accessToken, subscriptionId);
      }
    } catch (error) {
      console.warn('Não foi possível registrar o OneSignal para este usuário.', error);
    }
  }

  async function handleLogin() {
    if (!password.trim()) {
      setErrorMessage("Informe sua senha.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage("");
    setInfoMessage("");

    try {
      const response = await login({ email: normalizedEmail, password: password.trim() });
      await finishAuth(response.access_token, undefined, password.trim(), rememberMe);
    } catch (error) {
      setErrorMessage(error instanceof ApiRequestError ? error.message : 'Não foi possível entrar.');
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleRequestReset(isResend = false) {
    if (!normalizedEmail) {
      setErrorMessage("Informe seu endereço de e-mail.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage("");
    setInfoMessage("");

    try {
      await requestPasswordReset(normalizedEmail);
      if (isResend) {
        setInfoMessage("Enviamos um novo código.");
      } else {
        setStep("reset");
      }
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Não foi possível enviar o código.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleConfirmReset() {
    if (resetCode.length !== 6) {
      setErrorMessage("Informe o código de 6 dígitos.");
      return;
    }
    if (newPassword.length < 8) {
      setErrorMessage("A senha precisa ter pelo menos 8 caracteres.");
      return;
    }
    if (newPassword !== confirmNewPassword) {
      setErrorMessage("As senhas não conferem.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage("");
    setInfoMessage("");

    try {
      await confirmPasswordReset({
        email: normalizedEmail,
        code: resetCode,
        newPassword,
      });
      setResetCode("");
      setNewPassword("");
      setConfirmNewPassword("");
      setPassword("");
      setStep("password");
      setInfoMessage("Senha redefinida. Entre com a nova senha.");
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Não foi possível redefinir a senha.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCreateAccount() {
    if (!fullName) {
      setErrorMessage("Informe seu nome e sobrenome.");
      return;
    }
    if (signupForm.password.length < 8) {
      setErrorMessage("A senha precisa ter pelo menos 8 caracteres.");
      return;
    }
    if (signupForm.password !== signupForm.confirmPassword) {
      setErrorMessage('As senhas não conferem.');
      return;
    }
    if (!acceptedTerms) {
      setErrorMessage("Aceite os termos para criar sua conta.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage("");

    try {
      const response = await register({
        email: normalizedEmail,
        password: signupForm.password,
        avatar_url: signupForm.avatarUrl || undefined,
        birth_date: signupForm.birthDateIso || undefined,
        full_name: fullName,
      });
      await finishAuth(
        response.access_token,
        signupForm.avatarUrl,
        signupForm.password,
        rememberMe,
      );
    } catch (error) {
      if (error instanceof ApiRequestError && error.message.includes('cadastrado')) {
        setErrorMessage('Esse e-mail já está cadastrado. Volte e entre com sua senha.');
      } else {
        setErrorMessage(error instanceof Error ? error.message : 'Não foi possível criar sua conta.');
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handlePickAvatar() {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();

    if (!permission.granted) {
      Alert.alert('Permissão necessária', 'Permita acesso às suas fotos para escolher uma imagem de perfil.');
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
      ? `data:${asset.mimeType ?? "image/jpeg"};base64,${asset.base64}`
      : asset.uri;

    updateSignupField("avatarUrl", avatarUrl);
  }

  function handleSelectBirthDate(date: Date) {
    updateSignupField("birthDateIso", formatDateIso(date));
    updateSignupField("birthDate", formatDatePtBr(date));
    setIsBirthDatePickerOpen(false);
  }

  return (
    <View style={styles.screen}>
      <StatusBar style="dark" />
      {step === "landing" ? (
        <LandingAuthScreen
          onAccessAccount={() => setStep("email")}
        />
      ) : (
        <SafeAreaView edges={["top", "bottom"]} style={styles.keyboardArea}>
          <KeyboardAvoidingView
            behavior={Platform.OS === "ios" ? "padding" : undefined}
            style={styles.keyboardArea}
          >
            {step === "email" ? (
              <EmailAuthScreen
                email={email}
                errorMessage={errorMessage}
                isSubmitting={isSubmitting}
                onChangeEmail={(value) => {
                  setEmail(value);
                  setErrorMessage("");
                }}
                onContinue={handleEmailContinue}
              />
            ) : step === "password" ? (
              <PasswordAuthScreen
                errorMessage={errorMessage}
                infoMessage={infoMessage}
                isPasswordVisible={isPasswordVisible}
                isSubmitting={isSubmitting}
                onBack={goBack}
                rememberMe={rememberMe}
                onToggleRememberMe={() => setRememberMe((current) => !current)}
                onChangePassword={(value) => {
                  setPassword(value);
                  setErrorMessage("");
                }}
                onContinue={handleLogin}
                onForgotPassword={() => {
                  setErrorMessage("");
                  setInfoMessage("");
                  setStep("forgot");
                }}
                onTogglePassword={() =>
                  setIsPasswordVisible((current) => !current)
                }
                password={password}
              />
            ) : step === "forgot" ? (
              <ForgotPasswordScreen
                email={email}
                errorMessage={errorMessage}
                isSubmitting={isSubmitting}
                onBack={goBack}
                onChangeEmail={(value) => {
                  setEmail(value);
                  setErrorMessage("");
                }}
                onContinue={() => handleRequestReset(false)}
              />
            ) : step === "reset" ? (
              <ResetPasswordScreen
                code={resetCode}
                confirmPassword={confirmNewPassword}
                email={normalizedEmail}
                errorMessage={errorMessage}
                infoMessage={infoMessage}
                isPasswordVisible={isPasswordVisible}
                isSubmitting={isSubmitting}
                newPassword={newPassword}
                onBack={goBack}
                onChangeCode={(value) => {
                  setResetCode(value);
                  setErrorMessage("");
                }}
                onChangeConfirmPassword={(value) => {
                  setConfirmNewPassword(value);
                  setErrorMessage("");
                }}
                onChangeNewPassword={(value) => {
                  setNewPassword(value);
                  setErrorMessage("");
                }}
                onConfirm={handleConfirmReset}
                onResend={() => handleRequestReset(true)}
                onTogglePassword={() =>
                  setIsPasswordVisible((current) => !current)
                }
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
                onTogglePassword={() =>
                  setIsPasswordVisible((current) => !current)
                }
                onToggleTerms={() => {
                  setAcceptedTerms((current) => !current);
                  setErrorMessage("");
                }}
                isBirthDatePickerOpen={isBirthDatePickerOpen}
              />
            )}
          </KeyboardAvoidingView>
        </SafeAreaView>
      )}
    </View>
  );
}

function formatDateIso(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatDatePtBr(date: Date) {
  const day = String(date.getDate()).padStart(2, "0");
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const year = date.getFullYear();
  return `${day}/${month}/${year}`;
}

function nameFromEmail(value: string) {
  const localPart = value.split("@")[0] || "";
  const firstToken = localPart.split(/[._-]/)[0] || "";
  return firstToken
    ? firstToken.charAt(0).toUpperCase() + firstToken.slice(1)
    : "";
}
