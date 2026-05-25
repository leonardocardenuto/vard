import Svg, { Defs, LinearGradient, Stop, Text as SvgText, TSpan } from 'react-native-svg';

import { AUTH_GRADIENT_COLORS } from '../types/flow';

type AuthGradientTextProps = {
  fontFamily?: string;
  fontSize: number;
  fontWeight?: string;
  height: number;
  lineHeight?: number;
  text: string;
  textAnchor?: 'start' | 'middle';
  width: number;
  y?: number;
};

export function AuthGradientText({
  fontFamily = 'Poppins-ExtraBold',
  fontSize,
  fontWeight = '800',
  height,
  lineHeight = fontSize,
  text,
  textAnchor = 'start',
  width,
  y = fontSize,
}: AuthGradientTextProps) {
  const lines = text.split('\n');
  const x = textAnchor === 'middle' ? width / 2 : 0;

  return (
    <Svg height={height} viewBox={`0 0 ${width} ${height}`} width={width}>
      <Defs>
        <LinearGradient id="authTextGradient" x1="0" x2="1" y1="0" y2="0">
          <Stop offset="8%" stopColor={AUTH_GRADIENT_COLORS[0]} />
          <Stop offset="48%" stopColor={AUTH_GRADIENT_COLORS[1]} />
          <Stop offset="100%" stopColor={AUTH_GRADIENT_COLORS[2]} />
        </LinearGradient>
      </Defs>
      <SvgText
        fill="url(#authTextGradient)"
        fontFamily={fontFamily}
        fontSize={fontSize}
        fontWeight={fontWeight}
        textAnchor={textAnchor}
        x={x}
        y={y}
      >
        {lines.map((line, index) => (
          <TSpan dy={index === 0 ? 0 : lineHeight} key={`${line}-${index}`} x={x}>
            {line}
          </TSpan>
        ))}
      </SvgText>
    </Svg>
  );
}
