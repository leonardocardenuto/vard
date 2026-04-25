import { StyleSheet, Text, View } from 'react-native';

import { LayoutWithNavbar } from '../../../components/LayoutWithNavbar';

export function Settings() {
  return (
    <LayoutWithNavbar>
      <View style={styles.container}>
        <Text style={styles.title}>Ajustes</Text>
      </View>
    </LayoutWithNavbar>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    color: '#302611',
    fontSize: 22,
    fontWeight: '800',
  },
});
