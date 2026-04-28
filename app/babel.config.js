module.exports = function (api) {
  api.cache(true);

  return {
    presets: ['./node_modules/expo/node_modules/babel-preset-expo'],
  };
};
