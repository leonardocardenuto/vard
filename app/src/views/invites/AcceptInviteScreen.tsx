import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useNavigationState } from '@react-navigation/native';

import { ApiRequestError, acceptInvite } from '../../lib/api';
import { RootStackParamList } from '../../navigation/types';

type Props = NativeStackScreenProps<RootStackParamList, 'AcceptInvite'>;

export function AcceptInviteScreen({ navigation, route }: Props) {
  const { token } = route.params;
  const [phase, setPhase] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');

  const accessToken = useNavigationState((state) => {
    const appTabsRoute = state?.routes.find((r) => r.name === 'AppTabs');
    return (appTabsRoute?.params as { accessToken?: string } | undefined)?.accessToken ?? null;
  });

  const handleAccept = useCallback(async () => {
    if (!accessToken) return;
    setPhase('loading');
    try {
      await acceptInvite(accessToken, token);
      setPhase('success');
    } catch (err) {
      setPhase('error');
      setErrorMessage(err instanceof ApiRequestError ? err.message : 'Erro ao aceitar o convite.');
    }
  }, [accessToken, token]);

  useEffect(() => {
    if (accessToken && phase === 'idle') {
      void handleAccept();
    }
  }, [accessToken, phase, handleAccept]);

  useEffect(() => {
    if (!accessToken) {
      navigation.replace('Auth', {
        initialStep: 'email',
        pendingInviteToken: token,
      });
    }
  }, [accessToken, navigation, token]);

  function handleGoToWorkspace() {
    if (navigation.canGoBack()) {
      navigation.goBack();
    } else {
      navigation.navigate('AppTabs', undefined);
    }
  }

  if (!accessToken) {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>Você foi convidado!</Text>
        <Text style={styles.body}>Preparando seu convite...</Text>
      </View>
    );
  }

  if (phase === 'idle' || phase === 'loading') {
    return (
      <View style={styles.container}>
        <ActivityIndicator color="#019BDE" size="large" />
        <Text style={styles.body}>Aceitando convite...</Text>
      </View>
    );
  }

  if (phase === 'success') {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>Convite aceito!</Text>
        <Text style={styles.body}>Você agora faz parte do workspace.</Text>
        <Pressable onPress={handleGoToWorkspace} style={styles.primaryButton}>
          <Text style={styles.primaryButtonText}>Ver workspaces</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Erro ao aceitar convite</Text>
      <Text style={styles.body}>{errorMessage}</Text>
      <Pressable onPress={handleGoToWorkspace} style={styles.secondaryButton}>
        <Text style={styles.secondaryButtonText}>Voltar</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
    backgroundColor: '#FFFFFF',
    gap: 16,
  },
  title: {
    fontFamily: 'Poppins-Bold',
    fontSize: 22,
    color: '#111827',
    textAlign: 'center',
  },
  body: {
    fontFamily: 'Poppins-Regular',
    fontSize: 15,
    color: '#4B5563',
    textAlign: 'center',
    lineHeight: 22,
  },
  primaryButton: {
    backgroundColor: '#019BDE',
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 32,
    alignItems: 'center',
    width: '100%',
  },
  primaryButtonText: {
    fontFamily: 'Poppins-SemiBold',
    fontSize: 15,
    color: '#FFFFFF',
  },
  secondaryButton: {
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 32,
    alignItems: 'center',
    width: '100%',
    borderWidth: 1,
    borderColor: '#D1D5DB',
  },
  secondaryButtonText: {
    fontFamily: 'Poppins-SemiBold',
    fontSize: 15,
    color: '#374151',
  },
});
