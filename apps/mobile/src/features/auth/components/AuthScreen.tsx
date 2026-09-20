import React, { useContext } from "react";
import { StatusBar } from "expo-status-bar";
import {
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
    <View style={styles.container} testID={testID}>
      <StatusBar style="light" />
      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={[styles.scrollContent, contentContainerStyle]}
        bounces={false}
        contentInsetAdjustmentBehavior="never"
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="none"
        automaticallyAdjustKeyboardInsets={Platform.OS === "ios"}
        overScrollMode="never"
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.centerContainer}>{children}</View>
      </ScrollView>
    </View>
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
  container: {
    flex: 1,
    backgroundColor: colors.surface,
  },
  scrollView: {
    flex: 1,
    backgroundColor: colors.surface,
  },
  scrollContent: {
    flexGrow: 1,
    backgroundColor: colors.surface,
  },
  centerContainer: {
    flexGrow: 1,
    width: "100%",
    backgroundColor: colors.surface,
  },
  panel: {
    flex: 1,
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
