import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { colors, spacing, typography } from "../../theming/tokens";
import { Button } from "./Button";

export type ErrorStateProps = {
  title: string;
  message?: string;
  onRetry?: () => void;
  retryLabel?: string;
};

export function ErrorState({ title, message, onRetry, retryLabel = "Try again" }: ErrorStateProps) {
  return (
    <View style={styles.container} accessible accessibilityRole="alert" accessibilityLabel={title}>
      <Text style={styles.title} allowFontScaling>
        {title}
      </Text>
      {message ? (
        <Text style={styles.message} allowFontScaling>
          {message}
        </Text>
      ) : null}
      {onRetry ? <Button label={retryLabel} onPress={onRetry} variant="outline" /> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.md,
    padding: spacing.xl,
    backgroundColor: colors.tilePink,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#FFFFFF",
  },
  title: {
    fontSize: typography.fontSize.title,
    fontWeight: "800",
    color: colors.critical,
    textAlign: "center",
  },
  message: {
    fontSize: typography.fontSize.body,
    color: colors.textSecondary,
    textAlign: "center",
  },
});
