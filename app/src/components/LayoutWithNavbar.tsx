import { ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';

import { BottomNavigationBar } from './BottomNavigationBar';

type LayoutWithNavbarProps = {
  children: ReactNode;
};

export function LayoutWithNavbar({ children }: LayoutWithNavbarProps) {
  return (
    <View style={styles.container}>
      <View style={styles.content}>{children}</View>
      <BottomNavigationBar />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FBF5EC',
  },
  content: {
    flex: 1,
    paddingBottom: 108,
  },
});
