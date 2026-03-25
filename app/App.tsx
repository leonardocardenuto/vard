import { useEffect, useState } from 'react';
import { LinearGradient } from 'expo-linear-gradient';
import { StatusBar } from 'expo-status-bar';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import VardLogo from './assets/vard_logo.svg';

export default function App() {
  const [isSplashVisible, setIsSplashVisible] = useState(true);

  useEffect(() => {
    const timeout = setTimeout(() => {
      setIsSplashVisible(false);
    }, 1600);

    return () => clearTimeout(timeout);
  }, []);

  if (isSplashVisible) {
    return (
      <LinearGradient
        colors={['#03CDF4', '#019BDE', '#01EBD0']}
        locations={[0.01, 0.48, 1]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.container}
      >
        <View style={styles.content}>
          <VardLogo width={170} height={251} />
        </View>
        <StatusBar style="light" />
      </LinearGradient>
    );
  }

  return (
    <LinearGradient
      colors={['#03CDF4', '#019BDE', '#01EBD0']}
      locations={[0.01, 0.48, 1]}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
      style={styles.container}
    >
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.loginScreen}
      >
        <View style={styles.hero}>
          <VardLogo width={128} height={188} />
        </View>
        <View style={styles.sheet}>
          <ScrollView
            bounces={false}
            contentContainerStyle={styles.sheetContent}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            <Text style={styles.loginTitle}>Acessar conta</Text>

            <View style={styles.form}>
              <View style={styles.field}>
                <Text style={styles.fieldLabel}>E-mail</Text>
                <TextInput
                  autoCapitalize="none"
                  keyboardType="email-address"
                  placeholder="Seu e-mail"
                  placeholderTextColor="#91A0A7"
                  style={styles.input}
                />
              </View>

              <View style={styles.field}>
                <Text style={styles.fieldLabel}>Senha</Text>
                <TextInput
                  secureTextEntry
                  placeholder="Sua senha"
                  placeholderTextColor="#91A0A7"
                  style={styles.input}
                />
              </View>

              <Pressable style={styles.forgotButton}>
                <Text style={styles.forgotButtonLabel}>Esqueci minha senha</Text>
              </Pressable>

              <Pressable style={styles.button}>
                <Text style={styles.buttonLabel}>Entrar</Text>
              </Pressable>
            </View>
          </ScrollView>
        </View>
      </KeyboardAvoidingView>
      <StatusBar style="light" />
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  content: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  loginScreen: {
    flex: 1,
  },
  hero: {
    height: 280,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sheet: {
    flex: 1,
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 32,
    borderTopRightRadius: 32,
    marginTop: -22,
  },
  sheetContent: {
    flexGrow: 1,
    paddingHorizontal: 30,
    paddingTop: 36,
    paddingBottom: 30,
  },
  loginTitle: {
    alignItems: 'center',
    color: '#0A6A92',
    fontSize: 28,
    fontWeight: '700',
    textAlign: 'center',
    marginBottom: 30,
  },
  form: {
    gap: 22,
  },
  field: {
    borderBottomWidth: 1,
    borderBottomColor: '#C9D6DB',
    paddingBottom: 8,
  },
  fieldLabel: {
    color: '#0A6A92',
    fontSize: 14,
    fontWeight: '700',
    marginBottom: 6,
  },
  input: {
    minHeight: 36,
    paddingVertical: 0,
    color: '#17313D',
    fontSize: 18,
  },
  forgotButton: {
    alignSelf: 'flex-end',
    marginTop: -6,
  },
  forgotButtonLabel: {
    color: '#1A8BC3',
    fontSize: 14,
    fontWeight: '600',
  },
  button: {
    height: 52,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#0A6A92',
    marginTop: 8,
  },
  buttonLabel: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '700',
  },
});
