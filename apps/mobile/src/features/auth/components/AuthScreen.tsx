import React, { useContext } from "react";
import { StatusBar } from "expo-status-bar";
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  type StyleProp,
  View,
  type ViewStyle,
} from "react-native";
import { SafeAreaInsetsContext } from "react-native-safe-area-context";
import { colors, radii, spacing } from "../../../theming/tokens";

export type AuthScreenProps = {
  children: React.ReactNode;
  contentContainerStyle?: StyleProp<ViewStyle>;
  testID?: string;
};

export type AuthPanelProps = {
  children: React.ReactNode;
  overlapHeader?: boolean;
  style?: StyleProp<ViewStyle>;
};

export function AuthScreen({ children, contentContainerStyle, testID }: AuthScreenProps) {
  return (
    <KeyboardAvoidingView
      style={styles.keyboardAvoiding}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={Platform.OS === "ios" ? 40 : 0}
      testID={testID}
    >
      <StatusBar style="light" />
      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={[styles.scrollContent, contentContainerStyle]}
        bounces={false}
        contentInsetAdjustmentBehavior="never"
        keyboardShouldPersistTaps="always"
        overScrollMode="never"
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.centerContainer}>{children}</View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

export function AuthPanel({ children, overlapHeader = true, style }: AuthPanelProps) {
  const insets = useContext(SafeAreaInsetsContext) ?? {
    bottom: 0,
    left: 0,
    right: 0,
    top: 0,
  };

  return (
    <View
      style={[
        styles.panel,
        { paddingBottom: Math.max(spacing.lg, insets.bottom + spacing.md) },
        !overlapHeader && styles.panelFlush,
        style,
      ]}
    >
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  keyboardAvoiding: {
    flex: 1,
    backgroundColor: colors.primary,
  },
  scrollView: {
    flex: 1,
    backgroundColor: colors.primary,
  },
  scrollContent: {
    flexGrow: 1,
  },
  centerContainer: {
    flexGrow: 1,
    width: "100%",
    backgroundColor: colors.surface,
  },
  panel: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: 32,
    borderTopRightRadius: 32,
    marginTop: -spacing.xl,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    gap: spacing.md,
  },
  panelFlush: {
    marginTop: 0,
    borderTopLeftRadius: radii.lg,
    borderTopRightRadius: radii.lg,
  },
});
