import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { colors, spacing, typography } from "../../../theming/tokens";

export type AuthFooterProps = {
  text?: string;
};

export function AuthFooter({
  text = "Your information is protected by THALI × P.L.A.T.E. security controls.",
}: AuthFooterProps) {
  return (
    <View style={styles.container}>
      <Text style={styles.securityText} allowFontScaling>
        {text}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingVertical: spacing.sm,
    alignItems: "center",
  },
  securityText: {
    fontSize: typography.fontSize.caption,
    color: colors.textSecondary,
    textAlign: "center",
    lineHeight: 18,
  },
});
