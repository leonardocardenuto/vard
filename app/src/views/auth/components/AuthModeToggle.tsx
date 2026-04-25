import { Animated, Pressable, StyleSheet, Text, View } from 'react-native';

import { AuthMode } from '../types/auth';

type AuthModeToggleProps = {
  mode: AuthMode;
  onChangeMode: (mode: AuthMode) => void;
  toggleOffset: Animated.Value;
};

export function AuthModeToggle({ mode, onChangeMode, toggleOffset }: AuthModeToggleProps) {
  return (
    <View style={styles.toggle}>
      <Animated.View
        pointerEvents="none"
        style={[
          styles.toggleHighlight,
          {
            transform: [
              {
                translateX: toggleOffset.interpolate({
                  inputRange: [0, 1],
                  outputRange: [0, 102],
                }),
              },
            ],
          },
        ]}
      />
      <Pressable onPress={() => onChangeMode('login')} style={styles.toggleButton}>
        <Text style={[styles.toggleLabel, mode === 'login' && styles.toggleLabelActive]}>
          Entrar
        </Text>
      </Pressable>
      <Pressable onPress={() => onChangeMode('signup')} style={styles.toggleButton}>
        <Text style={[styles.toggleLabel, mode === 'signup' && styles.toggleLabelActive]}>
          Criar conta
        </Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  toggle: {
    position: 'relative',
    flexDirection: 'row',
    alignSelf: 'center',
    backgroundColor: '#F3E8D3',
    borderRadius: 16,
    padding: 4,
    marginBottom: 14,
  },
  toggleHighlight: {
    position: 'absolute',
    top: 4,
    left: 4,
    width: 102,
    bottom: 4,
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    shadowColor: '#8A7750',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.08,
    shadowRadius: 16,
    elevation: 2,
  },
  toggleButton: {
    minWidth: 102,
    paddingVertical: 7,
    paddingHorizontal: 12,
    borderRadius: 12,
    alignItems: 'center',
    zIndex: 1,
  },
  toggleLabel: {
    color: '#7F745F',
    fontSize: 14,
    fontWeight: '700',
  },
  toggleLabelActive: {
    color: '#302611',
  },
});
