import { useEffect, useMemo, useRef, useState } from 'react';
import { Animated, LayoutChangeEvent, Pressable, StyleSheet, Text, View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { BottomTabBarProps } from '@react-navigation/bottom-tabs';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { AppTabParamList } from '../navigation/types';

type NavItem = {
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  activeIcon: keyof typeof Ionicons.glyphMap;
  screen: keyof AppTabParamList;
};

const NAV_ITEMS: NavItem[] = [
  { label: 'INÍCIO', icon: 'home-outline', activeIcon: 'home', screen: 'Home' },
  { label: 'WORKSPACE', icon: 'grid-outline', activeIcon: 'grid', screen: 'Workspace' },
  { label: 'INSIGHTS', icon: 'sparkles-outline', activeIcon: 'sparkles', screen: 'Insights' },
  { label: 'AJUSTES', icon: 'settings-outline', activeIcon: 'settings', screen: 'Settings' },
];

const NAV_HORIZONTAL_PADDING = 16;

export function BottomNavigationBar({ navigation, state }: BottomTabBarProps) {
  const insets = useSafeAreaInsets();
  const styles = useMemo(() => createStyles(insets.bottom), [insets.bottom]);
  const [navWidth, setNavWidth] = useState(0);
  const activeIndex = state.index;
  const activeOffset = useRef(new Animated.Value(activeIndex)).current;

  useEffect(() => {
    Animated.spring(activeOffset, {
      toValue: activeIndex,
      useNativeDriver: true,
      damping: 20,
      mass: 0.9,
      stiffness: 180,
    }).start();
  }, [activeIndex, activeOffset]);

  const itemWidth = navWidth > 0 ? (navWidth - NAV_HORIZONTAL_PADDING * 2) / NAV_ITEMS.length : 0;

  function handleLayout(event: LayoutChangeEvent) {
    setNavWidth(event.nativeEvent.layout.width);
  }

  return (
    <View style={styles.container}>
      <View onLayout={handleLayout} style={styles.navbar}>
        {itemWidth > 0 ? (
          <Animated.View
            pointerEvents="none"
            style={[
              styles.activeHighlight,
              {
                width: itemWidth,
                transform: [{ translateX: Animated.multiply(activeOffset, itemWidth) }],
              },
            ]}
          >
            <LinearGradient
              colors={['#03CDF4', '#019BDE', '#01EBD0']}
              locations={[0.01, 0.48, 1]}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 1 }}
              style={styles.activeHighlightGradient}
            />
          </Animated.View>
        ) : null}

        {NAV_ITEMS.map((item) => {
          const routeIndex = state.routes.findIndex((route) => route.name === item.screen);
          const isActive = routeIndex === activeIndex;

          return (
            <Pressable
              key={item.screen}
              onPress={() => navigation.navigate(item.screen)}
              style={styles.navItem}
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
      paddingHorizontal: 0,
      paddingBottom: 0,
      zIndex: 10,
    },
    navbar: {
      width: '100%',
      minHeight: 72,
      backgroundColor: '#FFFFFF',
      borderWidth: 1,
      borderColor: '#E7EEF5',
      flexDirection: 'row',
      alignItems: 'center',
      paddingHorizontal: NAV_HORIZONTAL_PADDING,
      paddingTop: 10,
      paddingBottom: Math.max(bottomInset, 10),
      shadowColor: '#708195',
      shadowOffset: { width: 0, height: 10 },
      shadowOpacity: 0.26,
      shadowRadius: 24,
      elevation: 12,
      position: 'relative',
    },
    activeHighlight: {
      position: 'absolute',
      left: NAV_HORIZONTAL_PADDING,
      top: 10,
      height: 52,
      borderRadius: 16,
      shadowColor: '#05BFE6',
      shadowOffset: { width: 0, height: 10 },
      shadowOpacity: 0.26,
      shadowRadius: 16,
      elevation: 8,
    },
    activeHighlightGradient: {
      flex: 1,
      borderRadius: 16,
    },
    navItem: {
      flex: 1,
      height: 52,
      alignItems: 'center',
      justifyContent: 'center',
      gap: 4,
      zIndex: 1,
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
