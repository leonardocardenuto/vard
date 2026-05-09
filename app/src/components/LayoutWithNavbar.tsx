import { ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';

type LayoutWithNavbarProps = {
  children: ReactNode;
};

export function LayoutWithNavbar({ children }: LayoutWithNavbarProps) {
  return (
    <View style={styles.container}>
      <View style={styles.content}>{children}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F6FAFE',
  },
  content: {
    flex: 1,
    paddingBottom: 108,
  },
});
