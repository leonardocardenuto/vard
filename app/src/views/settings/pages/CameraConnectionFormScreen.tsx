import { Feather } from '@expo/vector-icons';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from 'react-native';

import { LayoutWithNavbar } from '../../../components/LayoutWithNavbar';
import {
  ApiRequestError,
  createCamera,
} from '../../../lib/api';
import { SettingsStackParamList } from '../types';
import { resolvePrimaryWorkspace } from '../utils/resolveWorkspace';
import { styles } from '../styles/CameraConnectionFormScreen';

type Props = NativeStackScreenProps<SettingsStackParamList, 'CameraConnectionForm'>;

type ConnectionProtocol = 'https-manual' | 'local-webview' | 'rtsp-config' | 'rtsp-manual';

type FormState = {
  host: string;
  name: string;
  password: string;
  path: string;
  streamUrl: string;
  username: string;
};

const initialFormState: FormState = {
  host: '',
  name: '',
  password: '',
  path: '/cam/realmonitor?channel=1&subtype=0',
  streamUrl: '',
  username: '',
};

const protocolOptions: Array<{
  description: string;
  label: string;
  value: ConnectionProtocol;
}> = [
  {
    value: 'local-webview',
    label: 'Câmera local',
    description: 'Você informa só o IP e o app abre o link local da câmera em WebView.',
  },
  {
    value: 'rtsp-config',
    label: 'RTSP com acesso',
    description: 'Monte a conexão com host, usuário, senha e caminho RTSP.',
  },
  {
    value: 'rtsp-manual',
    label: 'RTSP manual',
    description: 'Permite informar a URL RTSP completa de um equipamento compatível.',
  },
  {
    value: 'https-manual',
    label: 'HTTPS manual',
    description: 'Permite informar uma URL HTTPS direta do stream ou endpoint da câmera.',
  },
];

export function CameraConnectionFormScreen({ navigation, route }: Props) {
  const { accessToken, userEmail, userName } = route.params;

  const [protocol, setProtocol] = useState<ConnectionProtocol>('rtsp-config');
  const [form, setForm] = useState<FormState>(initialFormState);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  function updateField(field: keyof FormState, value: string) {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function handleSave() {
    const name = form.name.trim();

    if (!name) {
      setErrorMessage('Informe um nome para a câmera.');
      return;
    }

    let streamUrl = '';
    let metadata: Record<string, unknown> = {};

    if (protocol === 'local-webview') {
      const host = form.host.trim();

      if (!host) {
        setErrorMessage('Informe o IP ou URL da câmera local.');
        return;
      }

      streamUrl = host.startsWith('http://') || host.startsWith('https://')
        ? host
        : `http://${host}:8080/browserfs.html`;
      metadata = {
        host,
        protocol: 'local-webview',
      };
    } else if (protocol === 'rtsp-config') {
      const host = form.host.trim();
      const username = form.username.trim();
      const password = form.password.trim();
      const path = form.path.trim();

      if (!host || !username || !password || !path) {
        setErrorMessage('Preencha host, usuário, senha e caminho RTSP.');
        return;
      }

      const normalizedPath = path.startsWith('/') ? path : `/${path}`;
      streamUrl = `rtsp://${encodeURIComponent(username)}:${encodeURIComponent(password)}@${host}:554${normalizedPath}`;
      metadata = {
        host,
        path: normalizedPath,
        username,
      };
    } else {
      const manualUrl = form.streamUrl.trim();

      if (!manualUrl) {
        setErrorMessage(
          protocol === 'https-manual'
            ? 'Informe a URL HTTPS completa da câmera.'
            : 'Informe a URL RTSP completa da câmera.'
        );
        return;
      }

      streamUrl = manualUrl;
      metadata = {
        source: 'manual',
      };
    }

    setIsSaving(true);
    setErrorMessage('');

    try {
      const workspace = await resolvePrimaryWorkspace({
        accessToken,
        userEmail,
        userName,
      });

      await createCamera(accessToken, {
        workspace_id: workspace.id,
        name,
        connection_type:
          protocol === 'https-manual' || protocol === 'local-webview' ? 'https' : 'rtsp',
        stream_url: streamUrl,
        status: 'offline',
        is_active: true,
        metadata: {
          ...metadata,
          protocol,
        },
      });

      navigation.goBack();
    } catch (error) {
      setErrorMessage(
        error instanceof ApiRequestError ? error.message : 'Não foi possível salvar a câmera.'
      );
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <LayoutWithNavbar>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.flex}
      >
        <ScrollView
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.topSpacer} />

          <View style={styles.headerRow}>
            <Pressable onPress={() => navigation.goBack()} style={styles.backButton}>
              <Feather color="#111827" name="chevron-left" size={20} />
            </Pressable>
            <Text style={styles.headerTitle}>Nova câmera</Text>
          </View>

          <Text style={styles.subtitle}>
            Escolha o protocolo de conexão e preencha as informações do dispositivo.
          </Text>

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Protocolo de conexão</Text>

            {protocolOptions.map((option) => {
              const isSelected = protocol === option.value;

              return (
                <Pressable
                  key={option.value}
                  onPress={() => setProtocol(option.value)}
                  style={[styles.protocolCard, isSelected && styles.protocolCardActive]}
                >
                  <View style={styles.protocolTextWrap}>
                    <Text style={styles.protocolLabel}>{option.label}</Text>
                    <Text style={styles.protocolDescription}>{option.description}</Text>
                  </View>
                  <View style={[styles.radioOuter, isSelected && styles.radioOuterActive]}>
                    {isSelected ? <View style={styles.radioInner} /> : null}
                  </View>
                </Pressable>
              );
            })}
          </View>

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Dados da câmera</Text>

            <TextInput
              onChangeText={(value) => updateField('name', value)}
              placeholder="Nome da câmera"
              placeholderTextColor="#9AA4B2"
              style={styles.input}
              value={form.name}
            />

            {protocol === 'local-webview' ? (
              <TextInput
                autoCapitalize="none"
                onChangeText={(value) => updateField('host', value)}
                placeholder="IP da câmera"
                placeholderTextColor="#9AA4B2"
                style={styles.input}
                value={form.host}
              />
            ) : protocol === 'rtsp-config' ? (
              <>
                <TextInput
                  autoCapitalize="none"
                  onChangeText={(value) => updateField('host', value)}
                  placeholder="IP ou host"
                  placeholderTextColor="#9AA4B2"
                  style={styles.input}
                  value={form.host}
                />
                <TextInput
                  autoCapitalize="none"
                  onChangeText={(value) => updateField('username', value)}
                  placeholder="Usuário"
                  placeholderTextColor="#9AA4B2"
                  style={styles.input}
                  value={form.username}
                />
                <TextInput
                  autoCapitalize="none"
                  onChangeText={(value) => updateField('password', value)}
                  placeholder="Senha"
                  placeholderTextColor="#9AA4B2"
                  secureTextEntry
                  style={styles.input}
                  value={form.password}
                />
                <TextInput
                  autoCapitalize="none"
                  onChangeText={(value) => updateField('path', value)}
                  placeholder="/cam/stream"
                  placeholderTextColor="#9AA4B2"
                  style={styles.input}
                  value={form.path}
                />
              </>
            ) : (
              <TextInput
                autoCapitalize="none"
                onChangeText={(value) => updateField('streamUrl', value)}
                placeholder={
                  protocol === 'https-manual'
                    ? 'https://camera.exemplo.local/stream'
                    : 'rtsp://usuario:senha@ip:554/...'
                }
                placeholderTextColor="#9AA4B2"
                style={[styles.input, styles.multilineInput]}
                value={form.streamUrl}
              />
            )}
          </View>

          {errorMessage ? <Text style={styles.errorText}>{errorMessage}</Text> : null}

          <Pressable
            disabled={isSaving}
            onPress={handleSave}
            style={[styles.primaryButton, isSaving && styles.buttonDisabled]}
          >
            <Text style={styles.primaryButtonText}>
              {isSaving ? 'Salvando...' : 'Salvar câmera'}
            </Text>
          </Pressable>
        </ScrollView>
      </KeyboardAvoidingView>
    </LayoutWithNavbar>
  );
}

