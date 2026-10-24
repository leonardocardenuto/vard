import { Feather } from '@expo/vector-icons';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StatusBar, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import VardHorizontalLogo from '../../../assets/vard-logo.svg';
import { MobileMonitorProfile } from '../../lib/api';
import { cancelMobileFall, monitorAvailable, MonitorStatus, monitorStatus, startMobileFallMonitor, stopMobileFallMonitor } from '../../lib/mobileFallMonitor';
import { clearSession } from '../../lib/session';

export function ElderlyMonitorScreen({ accessToken, profile, onLogout }: {
  accessToken: string; profile: MobileMonitorProfile; onLogout: () => void;
}) {
  const [workspaceId, setWorkspaceId] = useState(profile.workspaces[0]?.id ?? '');
  const [status, setStatus] = useState<MonitorStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    let mounted = true;
    const update = async () => {
      try {
        const next = await monitorStatus();
        if (!mounted) return;
        if (next?.running && next.workspaceId && !profile.workspaces.some((w) => w.id === next.workspaceId)) {
          await stopMobileFallMonitor();
          return;
        }
        setStatus(next);
        if (next?.running && next.workspaceId) setWorkspaceId(next.workspaceId);
        setNow(Date.now());
      } catch { if (mounted) setError('Não foi possível consultar o monitoramento.'); }
    };
    void update();
    const timer = setInterval(() => void update(), 1000);
    return () => { mounted = false; clearInterval(timer); };
  }, [profile]);

  async function toggle() {
    setBusy(true); setError('');
    try {
      if (status?.running) await stopMobileFallMonitor();
      else await startMobileFallMonitor(accessToken, workspaceId);
      setStatus(await monitorStatus());
    } catch (e) { setError(e instanceof Error ? e.message : 'Não foi possível iniciar o monitoramento.'); }
    finally { setBusy(false); }
  }

  async function confirmSafe() {
    setBusy(true); setError('');
    try {
      await cancelMobileFall();
      setStatus(await monitorStatus());
    } catch (e) { setError(e instanceof Error ? e.message : 'Não foi possível cancelar o alerta.'); }
    finally { setBusy(false); }
  }

  const pending = Boolean(status?.pendingDeadline && status.pendingDeadline > now);
  const seconds = Math.max(0, Math.ceil(((status?.pendingDeadline ?? 0) - now) / 1000));
  const active = status?.running && status.sensorActive;
  const rearmSeconds = active && !pending ? Math.max(0, Math.ceil(((status?.rearmDeadline ?? 0) - now) / 1000)) : 0;
  return (
    <SafeAreaView style={styles.root}>
      <StatusBar barStyle="dark-content" />
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.brand} accessible accessibilityRole="image" accessibilityLabel="VARD">
          <VardHorizontalLogo height={22} />
        </View>
        <Text style={styles.title}>Sua proteção</Text>
        <Text style={styles.body}>Leve o celular no bolso da calça ou preso à cintura para monitorar possíveis quedas.</Text>
        {profile.workspaces.length > 1 ? <View style={styles.choices}>
          {profile.workspaces.map((workspace) => <Pressable key={workspace.id} disabled={status?.running || busy}
            onPress={() => setWorkspaceId(workspace.id)} style={[styles.choice, workspaceId === workspace.id && styles.selected]}>
            <Text style={styles.choiceText}>{workspace.name}</Text>
          </Pressable>)}
        </View> : <Text style={styles.workspace}>{profile.workspaces[0]?.name}</Text>}

        <View style={styles.card}>
          <Feather name={active ? 'shield' : 'pause-circle'} size={56} color={active ? '#00A6AD' : '#667085'} />
          <Text accessibilityLiveRegion="polite" style={styles.cardTitle}>{rearmSeconds > 0 ? `Retomando detecção em ${rearmSeconds}s` : active ? 'Monitoramento ativo' : status?.running ? 'Iniciando sensor…' : 'Monitoramento pausado'}</Text>
          <Text style={styles.body}>{active ? 'O celular está acompanhando seus movimentos, inclusive com a tela bloqueada.' : 'Ative a proteção para acompanhar possíveis quedas.'}</Text>
          <Text style={styles.note}>Ao detectar uma possível queda, buscamos a localização do celular para ajudar seu espaço a encontrar você. Permita a localização e mantenha o GPS ligado.</Text>
          {status?.running && !status.locationReady ? <Text style={styles.note}>Localização indisponível. Os alertas continuam ativos. Para incluir o local, pause e ative a proteção com a localização permitida e ligada.</Text> : null}
          {!monitorAvailable() ? <Text style={styles.error}>O monitoramento contínuo está disponível na versão Android do VARD.</Text> : null}
          <Pressable accessibilityRole="button" disabled={busy || !monitorAvailable() || !workspaceId}
            onPress={() => void toggle()} style={[styles.button, status?.running && styles.outline, busy && styles.disabled]}>
            {busy ? <ActivityIndicator color="#003984" /> : <Text style={[styles.buttonText, status?.running && styles.outlineText]}>
              {status?.running ? 'Pausar monitoramento' : 'Ativar proteção'}
            </Text>}
          </Pressable>
        </View>

        {pending ? <View accessibilityLiveRegion="assertive" style={[styles.card, styles.warning]}>
          <Text style={styles.cardTitle}>Você está bem?</Text>
          <Text style={styles.body}>Detectamos uma possível queda. Seu espaço será avisado em {seconds} segundos.</Text>
          <Pressable accessibilityRole="button" disabled={busy} onPress={() => void confirmSafe()} style={styles.button}>
            <Text style={styles.buttonText}>Estou bem!</Text>
          </Pressable>
        </View> : null}
        {status?.queued ? <Text accessibilityLiveRegion="polite" style={styles.body}>{status.queued} alerta(s) aguardando envio. Conecte o celular à internet.</Text> : null}
        {status?.lastSent ? <Text style={styles.body}>Último alerta enviado: {new Date(status.lastSent).toLocaleString('pt-BR')}</Text> : null}
        {error || status?.error ? <Text accessibilityLiveRegion="polite" style={styles.error}>{error || status?.error}</Text> : null}
        <Text style={styles.note}>Mantenha as notificações permitidas. Forçar a parada do aplicativo interrompe o monitoramento. A detecção pode não reconhecer todas as quedas.</Text>
        <Pressable onPress={() => void clearSession().then(onLogout)} style={styles.logout}>
          <Text style={styles.outlineText}>Sair da conta</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F5FAFE' },
  content: { padding: 24, gap: 18, flexGrow: 1 },
  brand: { alignItems: 'center', paddingVertical: 12 },
  title: { color: '#101828', fontSize: 28, fontFamily: 'Poppins-Bold' },
  body: { color: '#475467', fontSize: 16, lineHeight: 25, fontFamily: 'Poppins-Regular' },
  workspace: { color: '#003984', fontSize: 17, fontFamily: 'Poppins-SemiBold' },
  card: { padding: 22, gap: 18, backgroundColor: '#FFF', borderRadius: 20, borderWidth: 1, borderColor: '#D7E2EC' },
  cardTitle: { fontSize: 22, fontFamily: 'Poppins-SemiBold', color: '#101828' },
  button: { minHeight: 60, padding: 16, borderRadius: 14, backgroundColor: '#008C99', justifyContent: 'center', alignItems: 'center' },
  buttonText: { color: '#FFF', fontSize: 17, fontFamily: 'Poppins-SemiBold', textAlign: 'center' },
  outline: { backgroundColor: '#EDF5FA', borderWidth: 1, borderColor: '#D7E2EC' },
  outlineText: { color: '#003984', fontSize: 16, fontFamily: 'Poppins-SemiBold', textAlign: 'center' },
  disabled: { opacity: 0.6 },
  error: { color: '#B42318', fontSize: 15, lineHeight: 23 },
  warning: { backgroundColor: '#FFF4ED', borderColor: '#F79009' },
  note: { color: '#667085', fontSize: 13, lineHeight: 21 },
  logout: { alignItems: 'center', padding: 18, marginTop: 10 },
  choices: { gap: 8 },
  choice: { padding: 14, borderWidth: 1, borderColor: '#D7E2EC', borderRadius: 12 },
  selected: { backgroundColor: '#DDF7F5', borderColor: '#00A6AD' },
  choiceText: { color: '#003984', fontSize: 16 },
});
