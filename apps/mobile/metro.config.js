const { getDefaultConfig } = require("expo/metro-config");

const config = getDefaultConfig(__dirname);

// Support WebAssembly for wa-sqlite on web
config.resolver.assetExts.push("wasm");

module.exports = config;