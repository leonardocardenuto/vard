import { useEffect } from 'react';
import { StyleSheet, View, ViewStyle } from 'react-native';
import Svg, { Circle } from 'react-native-svg';
import Animated, {
  Easing,
  useAnimatedProps,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSequence,
  withTiming,
} from 'react-native-reanimated';

const AnimatedView = Animated.createAnimatedComponent(View);
const AnimatedCircle = Animated.createAnimatedComponent(Circle);

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
  const rotation = useSharedValue(0);
  const centerScale = useSharedValue(1);

  useEffect(() => {
    rotation.value = withRepeat(
      withTiming(360, {
        duration,
        easing: Easing.linear,
      }),
      -1
    );
  }, [duration, rotation]);

  useEffect(() => {
    centerScale.value = withRepeat(
      withSequence(
        withTiming(1.3, { duration: 400, easing: Easing.out(Easing.ease) }),
        withTiming(1, { duration: 400, easing: Easing.in(Easing.ease) })
      ),
      -1
    );
  }, [centerScale]);

  const rotateStyle = useAnimatedStyle(() => ({
    transform: [{ rotate: `${rotation.value}deg` }],
  }));

  const centerProps = useAnimatedProps(() => ({
    r: centerRadius * centerScale.value,
  }));

  const center = size / 2;
  const orbitY = center - size * 0.3;

  return (
    <View style={[styles.container, { width: size, height: size }, style]}>
      <Svg width={size} height={size}>
        <AnimatedCircle
          cx={center}
          cy={center}
          r={centerRadius}
          fill={dotColor}
          animatedProps={centerProps}
        />
      </Svg>

      <AnimatedView style={[styles.spinner, rotateStyle]}>
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
      </AnimatedView>
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
