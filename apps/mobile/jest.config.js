/** @type {import('jest').Config} */
module.exports = {
  preset: "jest-expo",
  testMatch: ["<rootDir>/test/components/**/*.test.{ts,tsx}"],
  passWithNoTests: true,
  setupFiles: ["<rootDir>/test/setup/jest.setup.ts"],
  setupFilesAfterEnv: ["@testing-library/react-native/matchers"],
};