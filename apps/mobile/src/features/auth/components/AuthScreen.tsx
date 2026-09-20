import React from "react";
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  View,
} from "react-native";
import { colors, spacing } from "../../../theming/tokens";

export type AuthScreenProps = {
  children: React.ReactNode;
  contentContainerStyle?: View["props"]["style"];
  testID?: string;
};

export function AuthScreen({ children, contentContainerStyle, testID }: AuthScreenProps) {
  return (
    <KeyboardAvoidingView
      style={styles.keyboardAvoiding}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={Platform.OS === "ios" ? 40 : 0}
      testID={testID}
    >
      <ScrollView
        contentContainerStyle={[styles.scrollContent, contentContainerStyle]}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.centerContainer}>{children}</View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  keyboardAvoiding: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: "center",
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.xl,
  },
  centerContainer: {
    width: "100%",
    maxWidth: 480,
    alignSelf: "center",
    gap: spacing.md,
  },
});
