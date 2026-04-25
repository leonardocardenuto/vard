import { useMemo } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation, useRoute } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { RootStackParamList } from '../navigation/types';

type NavItem = {
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  activeIcon: keyof typeof Ionicons.glyphMap;
  screen: keyof RootStackParamList;
};

const NAV_ITEMS: NavItem[] = [
  { label: 'INÍCIO', icon: 'home-outline', activeIcon: 'home', screen: 'Home' },
  { label: 'WORKSPACE', icon: 'grid-outline', activeIcon: 'grid', screen: 'Workspace' },
  { label: 'INSIGHTS', icon: 'sparkles-outline', activeIcon: 'sparkles', screen: 'Insights' },
  { label: 'AJUSTES', icon: 'settings-outline', activeIcon: 'settings', screen: 'Settings' },
];

export function BottomNavigationBar() {
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const route = useRoute();
  const styles = useMemo(() => createStyles(insets.bottom), [insets.bottom]);

  return (
    <View style={styles.container}>
      <View style={styles.navbar}>
        {NAV_ITEMS.map((item) => {
          const isActive = route.name === item.screen;

          return (
            <Pressable
              key={item.screen}
              onPress={() => navigation.navigate(item.screen as never)}
              style={[styles.navItem, isActive && styles.navItemActive]}
            >
              <Ionicons
                color={isActive ? '#FFFFFF' : '#9AA8BA'}
                name={isActive ? item.activeIcon : item.icon}
                size={isActive ? 24 : 22}
              />
              <Text style={[styles.navLabel, isActive && styles.navLabelActive]}>
                {item.label}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const createStyles = (bottomInset: number) =>
  StyleSheet.create({
    container: {
      position: 'absolute',
      left: 0,
      right: 0,
      bottom: 0,
      alignItems: 'center',
      paddingHorizontal: 18,
      paddingBottom: Math.max(bottomInset, 16),
      zIndex: 10,
    },
    navbar: {
      width: '100%',
      minHeight: 72,
      maxWidth: 430,
      backgroundColor: '#FFFFFF',
      borderWidth: 1,
      borderColor: '#E7EEF5',
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      paddingHorizontal: 16,
      paddingVertical: 10,
      shadowColor: '#708195',
      shadowOffset: { width: 0, height: 10 },
      shadowOpacity: 0.26,
      shadowRadius: 24,
      elevation: 12,
    },
    navItem: {
      minWidth: 66,
      height: 52,
      alignItems: 'center',
      justifyContent: 'center',
      gap: 4,
    },
    navItemActive: {
      minWidth: 88,
      backgroundColor: '#05BFE6',
      borderRadius: 16,
      shadowColor: '#05BFE6',
      shadowOffset: { width: 0, height: 10 },
      shadowOpacity: 0.26,
      shadowRadius: 16,
      elevation: 8,
    },
    navLabel: {
      color: '#8B98AA',
      fontSize: 10,
      lineHeight: 12,
      fontWeight: '700',
    },
    navLabelActive: {
      color: '#FFFFFF',
      fontSize: 10,
      lineHeight: 12,
      letterSpacing: 0,
    },
  });
