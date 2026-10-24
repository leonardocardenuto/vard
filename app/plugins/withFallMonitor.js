const { withAndroidManifest, withMainApplication, withAppBuildGradle, withDangerousMod } = require('@expo/config-plugins');
const fs = require('fs');
const path = require('path');

module.exports = function withFallMonitor(config) {
  config = withAndroidManifest(config, (config) => {
    const manifest = config.modResults.manifest;
    manifest['uses-permission'] ??= [];
    for (const name of ['FOREGROUND_SERVICE', 'FOREGROUND_SERVICE_SPECIAL_USE', 'FOREGROUND_SERVICE_LOCATION', 'ACCESS_COARSE_LOCATION', 'ACCESS_FINE_LOCATION', 'WAKE_LOCK', 'RECEIVE_BOOT_COMPLETED', 'POST_NOTIFICATIONS', 'VIBRATE']) {
      const permission = `android.permission.${name}`;
      if (!manifest['uses-permission'].some((item) => item.$['android:name'] === permission)) {
        manifest['uses-permission'].push({ $: { 'android:name': permission } });
      }
    }
    const app = manifest.application[0];
    app.service ??= [];
    app.service = app.service.filter((item) => item.$['android:name'] !== 'com.vard.app.fallmonitor.FallMonitorService');
    app.service.push({ $: {
      'android:name': 'com.vard.app.fallmonitor.FallMonitorService', 'android:exported': 'false',
      'android:foregroundServiceType': 'specialUse|location', 'android:stopWithTask': 'false',
    }, property: [{ $: {
      'android:name': 'android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE',
      'android:value': 'User-enabled continuous on-device accelerometer monitoring for possible falls, with visible status and cancellation before notifying family.',
    } }] });
    app.receiver ??= [];
    app.receiver = app.receiver.filter((item) => item.$['android:name'] !== 'com.vard.app.fallmonitor.MonitorBootReceiver');
    app.receiver.push({ $: { 'android:name': 'com.vard.app.fallmonitor.MonitorBootReceiver', 'android:exported': 'false' },
      'intent-filter': [{ action: [
        { $: { 'android:name': 'android.intent.action.BOOT_COMPLETED' } },
        { $: { 'android:name': 'android.intent.action.MY_PACKAGE_REPLACED' } },
      ] }],
    });
    // Monitoring credentials are bound to this installation's Android Keystore.
    app.$['android:allowBackup'] = 'false';
    // Local camera streams and the development API use HTTP, including in
    // standalone APKs where the debug manifest is not merged.
    app.$['android:usesCleartextTraffic'] = 'true';
    return config;
  });
  config = withMainApplication(config, (config) => {
    if (!config.modResults.contents.includes('FallNotificationSound.register(this)')) {
      config.modResults.contents = config.modResults.contents.replace(
        'super.onCreate()',
        'super.onCreate()\n    com.vard.app.fallmonitor.FallNotificationSound.register(this)',
      );
    }
    if (!config.modResults.contents.includes('add(com.vard.app.fallmonitor.FallMonitorPackage())')) {
      config.modResults.contents = config.modResults.contents.replace(
        'PackageList(this).packages.apply {',
        'PackageList(this).packages.apply {\n              add(com.vard.app.fallmonitor.FallMonitorPackage())',
      );
    }
    return config;
  });
  config = withAppBuildGradle(config, (config) => {
    if (!config.modResults.contents.includes('testImplementation("junit:junit:4.13.2")')) {
      config.modResults.contents = config.modResults.contents.replace('dependencies {', 'dependencies {\n    testImplementation("junit:junit:4.13.2")');
    }
    return config;
  });
  return withDangerousMod(config, ['android', async (config) => {
    const raw = path.join(config.modRequest.platformProjectRoot, 'app/src/main/res/raw');
    fs.mkdirSync(raw, { recursive: true });
    fs.copyFileSync(path.join(__dirname, '../assets/sounds/vard_fall_alert.wav'), path.join(raw, 'vard_fall_alert.wav'));
    const destination = path.join(config.modRequest.platformProjectRoot, 'app/src/main/java/com/vard/app/fallmonitor');
    fs.mkdirSync(destination, { recursive: true });
    for (const file of fs.readdirSync(path.join(__dirname, '../native/fallmonitor'))) {
      if (file.endsWith('.kt')) fs.copyFileSync(path.join(__dirname, '../native/fallmonitor', file), path.join(destination, file));
    }
    const testsDestination = path.join(config.modRequest.platformProjectRoot, 'app/src/test/java/com/vard/app/fallmonitor');
    fs.mkdirSync(testsDestination, { recursive: true });
    for (const file of fs.readdirSync(path.join(__dirname, '../native/tests'))) {
      if (file.endsWith('.kt')) fs.copyFileSync(path.join(__dirname, '../native/tests', file), path.join(testsDestination, file));
    }
    return config;
  }]);
};
