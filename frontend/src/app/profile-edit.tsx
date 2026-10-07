import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { router } from "expo-router";

import { api } from "@/lib/api";
import { requestErrorMessage } from "@/lib/requestFailure";
import { authService } from "@/services/authService";

interface Profile {
  full_name: string;
  email: string;
  phone_number: string | null;
  language: string;
  role?: string;
}

function getErrorMessage(error: unknown): string {
  return requestErrorMessage(error, "Unable to update your profile.");
}

export default function ProfileEdit() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [language, setLanguage] = useState("English");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get<Profile>("/api/auth/me");
      const profile = response.data;
      setFullName(profile.full_name ?? "");
      setEmail(profile.email ?? "");
      setPhoneNumber(profile.phone_number ?? "");
      setLanguage(profile.language === "Kiswahili" ? "Kiswahili" : "English");
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(load);
  }, [load]);

  const save = async () => {
    if (!fullName.trim()) {
      setError("Enter your name before saving.");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const response = await api.put<Profile>("/api/auth/me", {
        full_name: fullName.trim(),
        phone_number: phoneNumber.trim() || null,
        language,
      });
      await authService.storeUser(response.data);
      router.back();
    } catch (saveError) {
      setError(getErrorMessage(saveError));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color="#0B6623" />
        <Text style={styles.muted}>Loading account details…</Text>
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
      <Pressable onPress={() => router.back()} style={styles.backButton}>
        <Text style={styles.backText}>‹  Back to Profile</Text>
      </Pressable>
      <Text style={styles.title}>Account details</Text>
      <Text style={styles.description}>Update the personal information used in your profile.</Text>

      <Text style={styles.label}>Full name</Text>
      <TextInput
        autoCapitalize="words"
        editable={!saving}
        onChangeText={setFullName}
        style={styles.input}
        value={fullName}
      />

      <Text style={styles.label}>Email address</Text>
      <TextInput editable={false} style={[styles.input, styles.readOnly]} value={email} />
      <Text style={styles.hint}>Contact support to change the sign-in email address.</Text>

      <Text style={styles.label}>Phone number</Text>
      <TextInput
        keyboardType="phone-pad"
        editable={!saving}
        onChangeText={setPhoneNumber}
        placeholder="Optional"
        style={styles.input}
        value={phoneNumber}
      />

      <Text style={styles.label}>Preferred language</Text>
      <View style={styles.languages}>
        {["English", "Kiswahili"].map((item) => (
          <Pressable
            accessibilityRole="button"
            accessibilityState={{ selected: language === item }}
            key={item}
            onPress={() => setLanguage(item)}
            style={[styles.language, language === item && styles.languageSelected]}
          >
            <Text style={[styles.languageText, language === item && styles.languageTextSelected]}>
              {item}
            </Text>
          </Pressable>
        ))}
      </View>

      {error && <Text accessibilityRole="alert" style={styles.error}>{error}</Text>}

      <Pressable
        accessibilityRole="button"
        disabled={saving}
        onPress={() => void save()}
        style={[styles.saveButton, saving && styles.disabled]}
      >
        {saving ? <ActivityIndicator color="#fff" /> : <Text style={styles.saveText}>Save changes</Text>}
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flexGrow: 1, padding: 22, backgroundColor: "#fff" },
  center: { flex: 1, alignItems: "center", justifyContent: "center", gap: 12 },
  muted: { color: "#68736b" },
  backButton: { alignSelf: "flex-start", paddingVertical: 8, marginBottom: 12 },
  backText: { color: "#0B6623", fontWeight: "700" },
  title: { color: "#17351f", fontSize: 27, fontWeight: "800" },
  description: { color: "#68736b", marginTop: 7, marginBottom: 22 },
  label: { color: "#27362b", fontWeight: "700", marginBottom: 7, marginTop: 12 },
  input: { borderColor: "#d8e0da", borderWidth: 1, borderRadius: 10, padding: 13, color: "#26332a" },
  readOnly: { backgroundColor: "#f2f4f2", color: "#68736b" },
  hint: { color: "#68736b", fontSize: 12, marginTop: 5 },
  languages: { flexDirection: "row", gap: 10 },
  language: { borderWidth: 1, borderColor: "#d8e0da", borderRadius: 10, padding: 12 },
  languageSelected: { borderColor: "#0B6623", backgroundColor: "#e7f3e9" },
  languageText: { color: "#26332a" },
  languageTextSelected: { color: "#0B6623", fontWeight: "700" },
  error: { color: "#982c20", backgroundColor: "#fff1f0", padding: 12, borderRadius: 8, marginTop: 18 },
  saveButton: { backgroundColor: "#0B6623", borderRadius: 10, padding: 16, alignItems: "center", marginTop: 24 },
  saveText: { color: "#fff", fontWeight: "700", fontSize: 16 },
  disabled: { opacity: 0.6 },
});
