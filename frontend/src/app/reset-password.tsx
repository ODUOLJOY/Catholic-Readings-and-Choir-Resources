import { useLocalSearchParams, router } from "expo-router";
import { useState } from "react";
import { Alert, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { api } from "@/lib/api";

export default function ResetPassword() {
  const { token } = useLocalSearchParams<{ token?: string }>();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saving, setSaving] = useState(false);

  async function resetPassword() {
    if (!token || !password || password !== confirm) {
      Alert.alert("Invalid password", "Enter matching passwords and use a valid reset link.");
      return;
    }
    try {
      setSaving(true);
      await api.post("/api/auth/reset-password", null, { params: { token, password } });
      Alert.alert("Password updated", "You can now sign in with your new password.");
      router.replace("/(auth)/login");
    } catch (error: any) {
      Alert.alert("Reset failed", error?.response?.data?.detail || "The reset link is invalid or expired.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Reset Password</Text>
      <TextInput style={styles.input} placeholder="New password" secureTextEntry value={password} onChangeText={setPassword} editable={!saving} />
      <TextInput style={styles.input} placeholder="Confirm password" secureTextEntry value={confirm} onChangeText={setConfirm} editable={!saving} />
      <Pressable style={styles.button} onPress={resetPassword} disabled={saving}>
        <Text style={styles.buttonText}>{saving ? "Updating..." : "Update Password"}</Text>
      </Pressable>
      <Pressable onPress={() => router.replace("/(auth)/login")}>
        <Text style={styles.link}>Back to login</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: "center", padding: 24, backgroundColor: "#F7F9F7" },
  title: { fontSize: 28, fontWeight: "800", color: "#0B6623", marginBottom: 24, textAlign: "center" },
  input: { backgroundColor: "#fff", borderWidth: 1, borderColor: "#D6DED8", borderRadius: 10, padding: 14, marginBottom: 14 },
  button: { backgroundColor: "#0B6623", borderRadius: 10, padding: 15, alignItems: "center" },
  buttonText: { color: "#fff", fontWeight: "800" },
  link: { color: "#0B6623", textAlign: "center", fontWeight: "700", marginTop: 20 },
});
