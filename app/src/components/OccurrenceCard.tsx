import { MobileFallLocation } from './MobileFallLocation';
import { Feather } from '@expo/vector-icons';
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { ApiRequestError, getNotification, NotificationResponse, updateNotification } from '../lib/api';
import { VARD_COLORS } from '../theme/vardTheme';

export function OccurrenceCard({ notification, workspaceName, accessToken, canOpenClip = false,
  opening = false, onOpen, validation = false, onUpdate }: {
  notification: NotificationResponse;
  workspaceName?: string;
  accessToken: string;
  canOpenClip?: boolean;
  opening?: boolean;
  onOpen?: () => void;
  validation?: boolean;
  onUpdate?: (updated: NotificationResponse) => void;
}) {
  const [payload, setPayload] = useState(notification.payload);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const savingRef = useRef(false);
  useEffect(() => { setPayload(notification.payload); }, [notification.payload]);
  const answer = payload.detection_validation as { is_valid?: boolean } | undefined;
  const resolution = payload.incident_resolution as { status?: string } | undefined;
  const selected = typeof answer?.is_valid === 'boolean' ? answer.is_valid
    : resolution?.status === 'false_positive' ? false
    : resolution?.status === 'confirmed' || resolution?.status === 'resolved' ? true : null;
  const isFall = /fall|queda/i.test(`${notification.notification_type} ${notification.title}`);
  const title = isFall ? (payload.source === 'accelerometer' ? 'Possível queda pelo celular' : 'Queda detectada') : notification.title;
  const isMobileFall = payload.source === 'accelerometer';
  const openAction = isMobileFall ? undefined : onOpen;

  async function validate(isValid: boolean) {
    if (savingRef.current || selected === isValid) return;
    savingRef.current = true;
    setSaving(true); setError('');
    try {
      const latest = await getNotification(accessToken, notification.id);
      const updated = await updateNotification(accessToken, notification.id, { payload: {
        ...latest.payload,
        detection_validation: { answered_at: new Date().toISOString(), is_valid: isValid },
        incident_resolution: {
          ...(typeof latest.payload.incident_resolution === 'object' && latest.payload.incident_resolution !== null
            ? latest.payload.incident_resolution : {}),
          status: isValid ? 'confirmed' : 'false_positive',
          updated_at: new Date().toISOString(),
        },
      } });
      setPayload(updated.payload);
      onUpdate?.(updated);
    } catch (e) {
      setError(e instanceof ApiRequestError && e.status === 403
        ? 'Seu perfil não tem permissão para avaliar esta detecção.'
        : 'Não foi possível salvar. Tente novamente.');
    } finally { savingRef.current = false; setSaving(false); }
  }

  return (
    <View style={styles.card}>
      <Pressable accessibilityRole={openAction ? 'button' : undefined}
        accessibilityLabel={openAction ? `${canOpenClip ? 'Visualizar trecho de' : 'Abrir'} ${title}` : undefined}
        disabled={!openAction || opening} onPress={openAction}
        style={({ pressed }) => [styles.main, pressed && styles.pressed]}>
        <View style={styles.icon}><Feather color="#B42318" name="alert-triangle" size={20} /></View>
        <View style={styles.content}>
          <Text style={styles.title}>{title}</Text>
          {workspaceName ? <Text style={styles.workspace}>{workspaceName}</Text> : null}
          <Text style={styles.body}>{notification.body}</Text>
          <MobileFallLocation payload={payload} />
          <View style={styles.footer}>
            <Text style={styles.date}>{new Date(notification.created_at).toLocaleString('pt-BR', {
              day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
            })}</Text>
            {isMobileFall ? null : opening ? <ActivityIndicator color={VARD_COLORS.primary} size="small" /> : openAction ? (
              <View style={styles.action}>
                <Feather color={VARD_COLORS.secondary} name={canOpenClip ? 'play-circle' : 'chevron-right'} size={16} />
                <Text style={styles.actionText}>{canOpenClip ? 'Ver trecho' : 'Ver detalhes'}</Text>
              </View>
            ) : <Text style={styles.date}>Sem trecho</Text>}
          </View>
        </View>
      </Pressable>
      {validation ? <View style={styles.validation}>
        <Text accessibilityLiveRegion="polite" style={styles.validationLabel}>
          {saving ? 'Salvando…' : selected === null ? 'A detecção é válida?' : selected ? 'Detecção válida' : 'Detecção inválida'}
        </Text>
        {([true, false] as const).map((value) => <Pressable key={String(value)} accessibilityRole="button"
          accessibilityLabel={value ? 'Marcar detecção como válida' : 'Marcar detecção como inválida'}
          accessibilityState={{ selected: selected === value, disabled: saving }} disabled={saving}
          onPress={() => void validate(value)} style={[styles.vote, selected === value && (value ? styles.yes : styles.no)]}>
          <Feather name={value ? 'thumbs-up' : 'thumbs-down'} size={18}
            color={selected === value ? (value ? '#027A48' : '#B42318') : '#667085'} />
        </Pressable>)}
      </View> : null}
      {error ? <Text accessibilityLiveRegion="polite" style={styles.error}>{error}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: VARD_COLORS.surface, borderColor: VARD_COLORS.border, borderWidth: 1, borderRadius: 14, overflow: 'hidden' },
  main: { padding: 14, flexDirection: 'row', alignItems: 'flex-start' },
  pressed: { backgroundColor: VARD_COLORS.background },
  icon: { width: 42, height: 42, borderRadius: 12, backgroundColor: '#FEF3F2', alignItems: 'center', justifyContent: 'center' },
  content: { flex: 1, marginLeft: 12 },
  title: { color: VARD_COLORS.text, fontFamily: 'Poppins-SemiBold', fontSize: 14 },
  workspace: { color: VARD_COLORS.secondary, fontFamily: 'Poppins-Medium', fontSize: 11, marginTop: 3 },
  body: { color: '#475467', fontFamily: 'Poppins-Regular', fontSize: 12, lineHeight: 18, marginTop: 3 },
  footer: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 6, marginTop: 9 },
  date: { color: '#98A2B3', fontFamily: 'Poppins-Medium', fontSize: 10 },
  action: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  actionText: { color: VARD_COLORS.secondary, fontFamily: 'Poppins-SemiBold', fontSize: 11 },
  validation: { borderTopWidth: 1, borderTopColor: VARD_COLORS.border, paddingHorizontal: 14, paddingVertical: 8, flexDirection: 'row', alignItems: 'center', gap: 8 },
  validationLabel: { flex: 1, fontFamily: 'Poppins-Medium', color: '#667085', fontSize: 11 },
  vote: { width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F2F4F7' },
  yes: { backgroundColor: '#ECFDF3' },
  no: { backgroundColor: '#FEF3F2' },
  error: { color: '#B42318', fontFamily: 'Poppins-Regular', fontSize: 12, paddingHorizontal: 14, paddingBottom: 12 },
});
