import React from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

/**
 * Shared loading, error and empty presentations.
 *
 * These exist because every community screen previously hand-rolled the same
 * three blocks with slightly different wording, which is how an alert box ends up
 * hiding a failure that the member never sees. Centralizing them keeps the
 * retry affordance present on all of them.
 */

const palette = {
  brand: "#0B6623",
  danger: "#8A1C13",
  dangerBackground: "#FDECEA",
  dangerBorder: "#F3C2BD",
  muted: "#657168",
};

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <View style={styles.center}>
      <ActivityIndicator color={palette.brand} size="large" />
      <Text style={styles.loadingLabel}>{label}</Text>
    </View>
  );
}

export function ErrorState({
  message,
  onRetry,
  retryLabel = "Try again",
}: {
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
}) {
  return (
    <View style={styles.errorBanner}>
      <Text style={styles.errorText}>{message}</Text>
      {onRetry ? (
        <Pressable style={styles.retryButton} onPress={onRetry} accessibilityRole="button">
          <Text style={styles.retryText}>{retryLabel}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

export function EmptyState({ message }: { message: string }) {
  return <Text style={styles.empty}>{message}</Text>;
}

export function SectionHeading({ children }: { children: React.ReactNode }) {
  return <Text style={styles.sectionHeading}>{children}</Text>;
}

const styles = StyleSheet.create({
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  },
  loadingLabel: {
    color: palette.muted,
    marginTop: 12,
  },
  errorBanner: {
    backgroundColor: palette.dangerBackground,
    borderColor: palette.dangerBorder,
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    marginTop: 12,
    gap: 8,
  },
  errorText: {
    color: palette.danger,
    lineHeight: 20,
  },
  retryButton: {
    alignSelf: "flex-start",
    backgroundColor: palette.danger,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
  },
  retryText: {
    color: "#fff",
    fontWeight: "700",
  },
  empty: {
    color: palette.muted,
    paddingVertical: 12,
    lineHeight: 20,
  },
  sectionHeading: {
    fontSize: 19,
    fontWeight: "700",
    color: "#183D24",
    marginTop: 22,
    marginBottom: 10,
  },
});