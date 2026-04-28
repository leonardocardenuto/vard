import Svg, {
  Defs,
  LinearGradient,
  Path,
  Rect,
  Stop,
  Text as SvgText,
} from 'react-native-svg';

type VardLogoProps = {
  width?: number;
};

export function VardLogo({ width = 220 }: VardLogoProps) {
  const height = width * 0.42;

  return (
    <Svg width={width} height={height} viewBox="0 0 520 220" fill="none">
      <Defs>
        <LinearGradient id="logoGradient" x1="22" y1="18" x2="180" y2="194" gradientUnits="userSpaceOnUse">
          <Stop offset="0.01" stopColor="#03CDF4" />
          <Stop offset="0.48" stopColor="#019BDE" />
          <Stop offset="1" stopColor="#01EBD0" />
        </LinearGradient>
      </Defs>

      <Rect x="22" y="18" width="156" height="184" rx="40" fill="url(#logoGradient)" />
      <Path
        d="M62 58L100 162L122 98L145 162L183 58H154L133 124L122 90L111 124L91 58H62Z"
        fill="#021B2D"
      />
      <SvgText
        x="216"
        y="133"
        fill="#FFFFFF"
        fontSize="84"
        fontWeight="800"
        letterSpacing="10"
      >
        VARD
      </SvgText>
    </Svg>
  );
}
