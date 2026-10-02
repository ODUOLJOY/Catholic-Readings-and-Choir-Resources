import { ActivityIndicator, StyleSheet, Text, View } from "react-native";

/**
 * OAuth redirect landing for Google authorization-code flow.
 * WebBrowser.openAuthSessionAsync captures this URL; the page itself
 * only needs to exist so the redirect URI resolves on web.
 */
export default function GoogleAuthCallbackScreen() {
  return (
    <View style={styles.container}>
      <ActivityIndicator size="large" color="#1B4F72" />
      <Text style={styles.text}>Completing Google sign-in…</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#F7F9FC",
    gap: 16,
    padding: 24,
  },
  text: {
    fontSize: 16,
    color: "#1B4F72",
    textAlign: "center",
  },
});
