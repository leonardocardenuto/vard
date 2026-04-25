import { RouteProp, useRoute } from '@react-navigation/native';
import { StyleSheet, Text, View } from 'react-native';

import { LayoutWithNavbar } from '../../../components/LayoutWithNavbar';
import { AppTabParamList } from '../../../navigation/types';

type HomeRoute = RouteProp<AppTabParamList, 'Home'>;

export function Home() {
  const route = useRoute<HomeRoute>();
  const userName = route.params?.userName?.trim() || 'usuário';

  return (
    <LayoutWithNavbar>
      <View style={styles.container}>
        <Text style={styles.title}>Bem-vindo, {userName}</Text>
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
    textAlign: 'center',
  },
});
