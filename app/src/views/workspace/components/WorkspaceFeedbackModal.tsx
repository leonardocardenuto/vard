import { Feather } from '@expo/vector-icons';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';

export type WorkspaceFeedback = {
  message: string;
  title: string;
  tone?: 'error' | 'info' | 'success' | 'warning';
};

type Props = {
  feedback: WorkspaceFeedback | null;
  onClose: () => void;
};

const toneConfig = {
  error: { background: '#FEE4E2', color: '#B42318', icon: 'x-circle' as const },
  info: { background: '#EAF4FF', color: '#00326D', icon: 'info' as const },
  success: { background: '#E7F8EF', color: '#067647', icon: 'check-circle' as const },
  warning: { background: '#FFF4E5', color: '#B54708', icon: 'alert-circle' as const },
};

export function WorkspaceFeedbackModal({ feedback, onClose }: Props) {
  const tone = feedback?.tone ?? 'info';
  const config = toneConfig[tone];

  return (
    <Modal animationType="fade" onRequestClose={onClose} transparent visible={feedback !== null}>
      <Pressable accessibilityLabel="Fechar feedback" onPress={onClose} style={styles.overlay}>
        <Pressable accessibilityViewIsModal onPress={() => undefined} style={styles.card}>
          <View style={[styles.iconWrap, { backgroundColor: config.background }]}>
            <Feather color={config.color} name={config.icon} size={26} />
          </View>
          <Text accessibilityRole="header" style={styles.title}>
            {feedback?.title}
          </Text>
          <Text style={styles.message}>{feedback?.message}</Text>
          <Pressable
            accessibilityLabel="Entendi"
            accessibilityRole="button"
            onPress={onClose}
            style={({ pressed }) => [styles.button, pressed && styles.buttonPressed]}
          >
            <Text style={styles.buttonText}>Entendi</Text>
          </Pressable>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    alignItems: 'center',
    backgroundColor: 'rgba(16, 24, 40, 0.48)',
    flex: 1,
    justifyContent: 'center',
    paddingHorizontal: 24,
  },
  card: {
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 24,
    paddingBottom: 22,
    paddingHorizontal: 22,
    paddingTop: 24,
    width: '100%',
  },
  iconWrap: {
    alignItems: 'center',
    borderRadius: 999,
    height: 56,
    justifyContent: 'center',
    width: 56,
  },
  title: {
    color: '#101828',
    fontFamily: 'Poppins-Bold',
    fontSize: 20,
    lineHeight: 28,
    marginTop: 14,
    textAlign: 'center',
  },
  message: {
    color: '#667085',
    fontFamily: 'Poppins-Regular',
    fontSize: 14,
    lineHeight: 21,
    marginTop: 6,
    textAlign: 'center',
  },
  button: {
    alignItems: 'center',
    backgroundColor: '#00326D',
    borderRadius: 14,
    justifyContent: 'center',
    marginTop: 20,
    minHeight: 50,
    width: '100%',
  },
  buttonPressed: {
    opacity: 0.78,
  },
  buttonText: {
    color: '#FFFFFF',
    fontFamily: 'Poppins-Bold',
    fontSize: 14,
  },
});
