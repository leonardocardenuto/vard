import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { getMe, getPushDelivery, PushProvider, sendTestPush } from '../lib/api';
import { getPushInstallationId, syncPushRegistration } from '../lib/pushNotifications';
import { VARD_COLORS } from '../theme/vardTheme';

export function PushTestPanel({ accessToken }: { accessToken: string }) {
  const [busy, setBusy] = useState<PushProvider | null>(null);
  const [message, setMessage] = useState('Compare o envio pelo OneSignal e pelo Firebase direto. Nenhuma ocorrência é criada.');
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  async function test(provider: PushProvider) {
    if (busy) return;
    setBusy(provider); setMessage('Registrando este aparelho…');
    try {
      const user = await getMe(accessToken);
      await syncPushRegistration(accessToken, user.id);
      if (!mounted.current) return;
      const result = await sendTestPush(accessToken, await getPushInstallationId(), provider);
      setMessage('Envio na fila. Aguardando o provedor…');
      for (let attempt = 0; attempt < 20; attempt++) {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        if (!mounted.current) return;
        const delivery = await getPushDelivery(accessToken, result.delivery_id);
        if (delivery.status === 'received') {
          const timing = delivery.timing_ms;
          const seconds = (ms: number | null) => ms === null ? '—' : `${(ms / 1000).toFixed(2)} s`;
          const total = delivery.receipt_source === 'foreground' ? 'Até confirmar no app' : 'Até confirmar ao tocar/abrir (inclui espera do usuário)';
          setMessage(`${total}: ${seconds(timing.confirmation)}. Fila: ${seconds(timing.queue)}. Resposta do provedor: ${seconds(timing.provider_request)}.`);
          return;
        }
        if (['failed', 'cancelled', 'expired'].includes(delivery.status)) {
          setMessage(`Envio não concluído: ${delivery.error ?? delivery.status}.`); return;
        }
        if (delivery.status === 'accepted') setMessage('Aceito pelo provedor. A confirmação do app ocorre ao receber em primeiro plano ou tocar na notificação.');
      }
    } catch (error) {
      if (mounted.current) setMessage(error instanceof Error ? error.message : 'Não foi possível enviar o teste.');
    } finally { if (mounted.current) setBusy(null); }
  }
  return <View style={styles.card}>
    <Text style={styles.title}>Testar notificações</Text>
    <Text accessibilityLiveRegion="polite" style={styles.body}>{message}</Text>
    <View style={styles.row}>
      {(['onesignal', 'fcm'] as const).map((provider) => <Pressable key={provider}
        accessibilityRole="button" disabled={busy !== null} onPress={() => void test(provider)}
        style={[styles.button, busy !== null && styles.disabled]}>
        {busy === provider ? <ActivityIndicator color={VARD_COLORS.secondary} /> : <Text style={styles.label}>
          {provider === 'fcm' ? 'FCM direto' : 'OneSignal'}
        </Text>}
      </Pressable>)}
    </View>
  </View>;
}
const styles = StyleSheet.create({
  card: { backgroundColor: VARD_COLORS.surface, borderRadius: 16, borderWidth: 1, borderColor: VARD_COLORS.border, padding: 18, gap: 12, marginTop: 16 },
  title: { fontFamily: 'Poppins-SemiBold', fontSize: 16, color: VARD_COLORS.text },
  body: { fontFamily: 'Poppins-Regular', fontSize: 12, lineHeight: 19, color: VARD_COLORS.muted },
  row: { flexDirection: 'row', gap: 10 },
  button: { flex: 1, minHeight: 48, backgroundColor: VARD_COLORS.primarySoft, borderRadius: 12, padding: 10, alignItems: 'center', justifyContent: 'center' },
  label: { fontFamily: 'Poppins-SemiBold', color: VARD_COLORS.secondary, fontSize: 13 },
  disabled: { opacity: 0.5 },
});
