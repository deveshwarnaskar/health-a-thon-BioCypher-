/** @type {import('jest').Config} */
module.exports = {
  preset: "jest-expo",
  testMatch: ["<rootDir>/test/components/**/*.test.{ts,tsx}"],
  passWithNoTests: true,
  setupFilesAfterEnv: ["@testing-library/react-native/matchers"],
};