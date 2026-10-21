const fs = require('node:fs');
const path = require('node:path');

module.exports = ({ config }) => {
  const mode = process.env.EXPO_PUBLIC_PUSH_MODE || 'onesignal';
  const googleServicesFile = process.env.GOOGLE_SERVICES_JSON || './google-services.json';
  const hasGoogleServices = fs.existsSync(path.resolve(__dirname, googleServicesFile));
  if (mode !== 'onesignal' && !hasGoogleServices) {
    throw new Error('FCM direto requer google-services.json ou GOOGLE_SERVICES_JSON.');
  }
  return {
    ...config,
    android: {
      ...config.android,
      ...(hasGoogleServices ? { googleServicesFile } : {}),
    },
  };
};
