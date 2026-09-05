const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);

config.transformer.babelTransformerPath = require.resolve('react-native-svg-transformer/expo');
config.resolver.assetExts = config.resolver.assetExts.filter((ext) => ext !== 'svg');
config.resolver.sourceExts.push('svg');

// Expo SDK 54's virtual env module reads .env even with EXPO_NO_DOTENV.
// Keep isolated Maestro runs on the API supplied by the test runner.
if (process.env.VARD_MAESTRO === '1') {
  const existing = config.resolver.blockList;
  config.resolver.blockList = [
    ...(Array.isArray(existing) ? existing : existing ? [existing] : []),
    /[/\\]\.env(?:\.[^/\\]+)?$/,
  ];
}

module.exports = config;
