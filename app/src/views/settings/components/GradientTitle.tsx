import Svg, {
  Defs,
  LinearGradient,
  Stop,
  Text as SvgText,
} from "react-native-svg";
import { VARD_COLORS } from "../../../theme/vardTheme";

type GradientTitleProps = {
  fontSize?: number;
  text: string;
  width?: number;
};

export function GradientTitle({
  fontSize = 40,
  text,
  width = 160,
}: GradientTitleProps) {
  const height = Math.round(fontSize * 1.05);

  return (
    <Svg height={height} viewBox={`0 0 ${width} ${height}`} width={width}>
      <Defs>
        <LinearGradient id="sharedTitleGradient" x1="0" x2="1" y1="0" y2="0">
          <Stop offset="0%" stopColor={VARD_COLORS.primary} />
          <Stop offset="100%" stopColor={VARD_COLORS.secondary} />
        </LinearGradient>
      </Defs>
      <SvgText
        fill="url(#sharedTitleGradient)"
        fontFamily="Poppins-SemiBold"
        fontSize={fontSize}
        x={0}
        y={Math.round(fontSize * 0.78)}
      >
        {text}
      </SvgText>
    </Svg>
  );
}
