import { useEffect, useRef } from 'react';
import { Animated, Easing, StyleSheet, View, ViewStyle } from 'react-native';
import Svg, { Circle } from 'react-native-svg';

export interface OrbitDotLoaderProps {
  dotColor?: string;
  dotRadius?: number;
  centerRadius?: number;
  size?: number;
  duration?: number;
  numDots?: number;
  style?: ViewStyle;
}

export function OrbitDotLoader({
  dotColor = '#fff',
  dotRadius = 4,
  centerRadius = 5,
  size = 40,
  duration = 900,
  numDots = 4,
  style,
}: OrbitDotLoaderProps) {
  const rotation = useRef(new Animated.Value(0)).current;
  const centerScale = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    const rotateAnimation = Animated.loop(
      Animated.timing(rotation, {
        toValue: 1,
        duration,
        easing: Easing.linear,
        useNativeDriver: true,
      })
    );
    const pulseAnimation = Animated.loop(
      Animated.sequence([
        Animated.timing(centerScale, {
          toValue: 1.3,
          duration: 400,
          easing: Easing.out(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(centerScale, {
          toValue: 1,
          duration: 400,
          easing: Easing.in(Easing.ease),
          useNativeDriver: true,
        }),
      ])
    );

    rotateAnimation.start();
    pulseAnimation.start();

    return () => {
      rotateAnimation.stop();
      pulseAnimation.stop();
      rotation.setValue(0);
      centerScale.setValue(1);
    };
  }, [centerScale, duration, rotation]);

  const rotate = rotation.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '360deg'],
  });

  const center = size / 2;
  const orbitY = center - size * 0.3;

  return (
    <View style={[styles.container, { width: size, height: size }, style]}>
      <Animated.View style={{ transform: [{ scale: centerScale }] }}>
        <Svg width={size} height={size}>
          <Circle
            cx={center}
            cy={center}
            r={centerRadius}
            fill={dotColor}
          />
        </Svg>
      </Animated.View>

      <Animated.View style={[styles.spinner, { transform: [{ rotate }] }]}>
        <Svg width={size} height={size}>
          {Array.from({ length: numDots }).map((_, index) => {
            const angle = (360 / numDots) * index;

            return (
              <Circle
                key={index}
                cx={center}
                cy={orbitY}
                r={dotRadius}
                fill={dotColor}
                transform={`rotate(${angle}, ${center}, ${center})`}
              />
            );
          })}
        </Svg>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  spinner: {
    position: 'absolute',
    justifyContent: 'center',
    alignItems: 'center',
  },
});
