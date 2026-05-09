import { Feather } from '@expo/vector-icons';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useState } from 'react';
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

import { LayoutWithNavbar } from '../../../components/LayoutWithNavbar';
import {
  ApiRequestError,
  createCamera,
} from '../../../lib/api';
import { SettingsStackParamList } from '../types';
import { resolvePrimaryWorkspace } from '../utils/resolveWorkspace';

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
    label: 'Camera local',
    description: 'Voce informa so o IP e o app abre o link local da camera em WebView.',
  },
  {
    value: 'rtsp-config',
    label: 'RTSP com acesso',
    description: 'Monte a conexao com host, usuario, senha e caminho RTSP.',
  },
  {
    value: 'rtsp-manual',
    label: 'RTSP manual',
    description: 'Permite informar a URL RTSP completa de um equipamento compativel.',
  },
  {
    value: 'https-manual',
    label: 'HTTPS manual',
    description: 'Permite informar uma URL HTTPS direta do stream ou endpoint da camera.',
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
      setErrorMessage('Informe um nome para a camera.');
      return;
    }

    let streamUrl = '';
    let metadata: Record<string, unknown> = {};

    if (protocol === 'local-webview') {
      const host = form.host.trim();

      if (!host) {
        setErrorMessage('Informe o IP ou URL da camera local.');
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
        setErrorMessage('Preencha host, usuario, senha e caminho RTSP.');
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
            ? 'Informe a URL HTTPS completa da camera.'
            : 'Informe a URL RTSP completa da camera.'
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
        error instanceof ApiRequestError ? error.message : 'Nao foi possivel salvar a camera.'
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
            <Text style={styles.headerTitle}>Nova camera</Text>
          </View>

          <Text style={styles.subtitle}>
            Escolha o protocolo de conexao e preencha as informacoes do dispositivo.
          </Text>

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Protocolo de conexao</Text>

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
            <Text style={styles.sectionTitle}>Dados da camera</Text>

            <TextInput
              onChangeText={(value) => updateField('name', value)}
              placeholder="Nome da camera"
              placeholderTextColor="#9AA4B2"
              style={styles.input}
              value={form.name}
            />

            {protocol === 'local-webview' ? (
              <TextInput
                autoCapitalize="none"
                onChangeText={(value) => updateField('host', value)}
                placeholder="IP da camera"
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
                  placeholder="Usuario"
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
              {isSaving ? 'Salvando...' : 'Salvar camera'}
            </Text>
          </Pressable>
        </ScrollView>
      </KeyboardAvoidingView>
    </LayoutWithNavbar>
  );
}

const styles = StyleSheet.create({
  flex: {
    flex: 1,
  },
  content: {
    paddingHorizontal: 22,
    paddingBottom: 144,
  },
  topSpacer: {
    height: 56,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  backButton: {
    width: 32,
    height: 32,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerTitle: {
    color: '#111827',
    fontSize: 22,
    fontWeight: '800',
  },
  subtitle: {
    marginTop: 8,
    marginBottom: 22,
    color: '#667085',
    fontSize: 14,
    lineHeight: 20,
  },
  section: {
    marginBottom: 18,
    padding: 16,
    borderRadius: 20,
    backgroundColor: '#FFFFFF',
    shadowColor: '#101828',
    shadowOpacity: 0.05,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 8 },
    elevation: 2,
  },
  sectionTitle: {
    color: '#111827',
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 12,
  },
  protocolCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 14,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    backgroundColor: '#FCFCFD',
    marginBottom: 10,
  },
  protocolCardActive: {
    borderColor: '#0BA5EC',
    backgroundColor: '#F0F9FF',
  },
  protocolTextWrap: {
    flex: 1,
    paddingRight: 12,
  },
  protocolLabel: {
    color: '#111827',
    fontSize: 15,
    fontWeight: '700',
  },
  protocolDescription: {
    color: '#667085',
    fontSize: 13,
    lineHeight: 18,
    marginTop: 4,
  },
  radioOuter: {
    width: 20,
    height: 20,
    borderRadius: 999,
    borderWidth: 2,
    borderColor: '#D0D5DD',
    alignItems: 'center',
    justifyContent: 'center',
  },
  radioOuterActive: {
    borderColor: '#0BA5EC',
  },
  radioInner: {
    width: 8,
    height: 8,
    borderRadius: 999,
    backgroundColor: '#0BA5EC',
  },
  input: {
    minHeight: 48,
    borderRadius: 14,
    backgroundColor: '#F8FAFC',
    borderWidth: 1,
    borderColor: '#E5E7EB',
    paddingHorizontal: 14,
    color: '#111827',
    fontSize: 14,
    marginBottom: 10,
  },
  multilineInput: {
    minHeight: 88,
    paddingTop: 14,
  },
  errorText: {
    marginBottom: 14,
    color: '#B42318',
    fontSize: 13,
    lineHeight: 18,
    fontWeight: '600',
  },
  primaryButton: {
    minHeight: 50,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#0BA5EC',
  },
  buttonDisabled: {
    opacity: 0.7,
  },
  primaryButtonText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '800',
  },
});
