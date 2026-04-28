import { StyleSheet, Text, View } from 'react-native';

import { LayoutWithNavbar } from '../../../components/LayoutWithNavbar';

export function Workspace() {
  return (
    <LayoutWithNavbar>
      <View style={styles.container}>
        <Text style={styles.title}>Workspace</Text>
        <Text style={styles.subtitle}>Seu espaço de trabalho fica aqui.</Text>
      </View>
    </LayoutWithNavbar>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 24,
  },
  title: {
    color: '#302611',
    fontSize: 24,
    lineHeight: 30,
    fontWeight: '800',
  },
  subtitle: {
    color: '#6F7B89',
    fontSize: 14,
    lineHeight: 20,
    marginTop: 8,
    textAlign: 'center',
  },
});
