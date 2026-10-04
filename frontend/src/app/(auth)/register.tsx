import { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { api } from "@/lib/api";
import { authService } from "@/services/authService";
import {
  HierarchyPicker,
  HierarchySelection,
} from "@/components/HierarchyPicker";

export default function RegisterScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [hierarchy, setHierarchy] = useState<HierarchySelection | null>(null);
  const [loading, setLoading] = useState(false);
  const [locationOptional, setLocationOptional] = useState(false);

  const parish = hierarchy?.parish ?? null;
  const parishLabel = parish ? `${parish.name}` : null;

  async function handleRegister() {
    if (!email || !password || !confirmPassword || !fullName) {
      Alert.alert("Error", "All fields are required");
      return;
    }

    if (password !== confirmPassword) {
      Alert.alert("Error", "Passwords do not match");
      return;
    }

    if (!parish && !locationOptional) {
      Alert.alert(
        "Error",
        "Select your province, diocese, deanery and parish, or tap Skip for now."
      );
      return;
    }

    setLoading(true);

    try {
      // Only the parish is submitted. The server derives the province,
      // diocese and deanery so the client can never send an inconsistent chain.
      await api.post(
        "/api/auth/register",
        {
          email: email.trim().toLowerCase(),
          password,
          full_name: fullName,
          parish_id: parish ? parish.id : null,
        },
        { timeout: 15000 }
      );

      await authService.login(email.trim().toLowerCase(), password);

      const user = await authService.getUser();
      // A user who picked a parish during sign-up is already located, so there
      // is no reason to send them through setup again.
      if (user && user.profile_setup_completed) {
        router.replace("/(tabs)");
      } else if (parish) {
        router.replace("/(tabs)");
      } else {
        router.replace("/profile-setup");
      }
    } catch (error: any) {
      let message = error?.response?.data?.detail || "Registration failed";

      if (error?.code === "ECONNABORTED") {
        message = "The server took too long to respond.";
      } else if (!error?.response) {
        message = "Could not connect to the server.";
      }

      Alert.alert("Registration Failed", message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.screen}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView
        contentContainerStyle={styles.container}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.header}>
          <Pressable onPress={() => router.back()} style={styles.backButton}>
            <Ionicons name="arrow-back" size={24} color="#0B6623" />
          </Pressable>
          <Text style={styles.title}>Create Account</Text>
        </View>

        <View style={styles.formCard}>
          <Text style={styles.label}>Full Name</Text>
          <View style={styles.inputWrapper}>
            <Ionicons name="person-outline" size={20} color="#777" />
            <TextInput
              style={styles.input}
              placeholder="Enter your full name"
              value={fullName}
              onChangeText={setFullName}
              editable={!loading}
            />
          </View>

          <Text style={styles.label}>Email Address</Text>
          <View style={styles.inputWrapper}>
            <Ionicons name="mail-outline" size={20} color="#777" />
            <TextInput
              style={styles.input}
              placeholder="Enter your email"
              value={email}
              onChangeText={setEmail}
              keyboardType="email-address"
              autoCapitalize="none"
              editable={!loading}
            />
          </View>

          <Text style={styles.label}>Password</Text>
          <View style={styles.inputWrapper}>
            <Ionicons name="lock-closed-outline" size={20} color="#777" />
            <TextInput
              style={styles.input}
              placeholder="Enter your password"
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              editable={!loading}
            />
          </View>

          <Text style={styles.label}>Confirm Password</Text>
          <View style={styles.inputWrapper}>
            <Ionicons name="lock-closed-outline" size={20} color="#777" />
            <TextInput
              style={styles.input}
              placeholder="Confirm your password"
              value={confirmPassword}
              onChangeText={setConfirmPassword}
              secureTextEntry
              editable={!loading}
            />
          </View>

          <Text style={styles.label}>Where do you belong?</Text>
          <Text style={styles.helpText}>
            Walk down the list to find your parish. This links your account to
            your parish community; it does not grant any administrative rights.
          </Text>

          <HierarchyPicker onChange={setHierarchy} />

          {parishLabel ? (
            <View style={styles.selectedBox}>
              <Ionicons
                name="checkmark-circle"
                size={18}
                color="#0B6623"
              />
              <Text style={styles.selectedText}>{parishLabel}</Text>
            </View>
          ) : null}

          {!parish ? (
            <Pressable
              accessibilityRole="button"
              disabled={loading}
              onPress={() => setLocationOptional(true)}
              style={styles.skipButton}
            >
              <Text style={styles.skipText}>I will choose my parish later</Text>
            </Pressable>
          ) : null}

          <Pressable
            style={[styles.button, loading && styles.buttonDisabled]}
            onPress={handleRegister}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.buttonText}>Create Account</Text>
            )}
          </Pressable>

          <View style={styles.footer}>
            <Text style={styles.footerText}>Already have an account? </Text>
            <Pressable onPress={() => router.replace("/login")}>
              <Text style={styles.link}>Sign In</Text>
            </Pressable>
          </View>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create<any>({
  screen: { flex: 1, backgroundColor: "#F7F9F7" },
  container: { padding: 20, paddingTop: 40, paddingBottom: 48 },
  header: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 30,
  },
  backButton: { padding: 10, marginRight: 10 },
  title: { fontSize: 24, fontWeight: "800", color: "#0B6623", flex: 1 },
  formCard: {
    backgroundColor: "#fff",
    borderRadius: 20,
    padding: 20,
    marginBottom: 20,
  },
  label: {
    fontSize: 14,
    fontWeight: "600",
    color: "#222",
    marginTop: 16,
    marginBottom: 8,
  },
  helpText: {
    color: "#68736b",
    fontSize: 13,
    lineHeight: 19,
    marginBottom: 14,
  },
  inputWrapper: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#E5EAE6",
    paddingHorizontal: 12,
    backgroundColor: "#F9FAFB",
  },
  input: {
    flex: 1,
    paddingVertical: 12,
    paddingHorizontal: 12,
    fontSize: 16,
    color: "#222",
  },
  selectedBox: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: "#e7f3e9",
    borderRadius: 10,
    padding: 12,
    marginTop: 14,
  },
  selectedText: { color: "#0B6623", fontWeight: "700", flex: 1 },
  skipButton: { alignItems: "center", paddingVertical: 14, marginTop: 8 },
  skipText: { color: "#0B6623", fontWeight: "600", fontSize: 14 },
  button: {
    backgroundColor: "#0B6623",
    borderRadius: 12,
    paddingVertical: 14,
    marginTop: 24,
    alignItems: "center",
  },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  footer: {
    flexDirection: "row",
    justifyContent: "center",
    marginTop: 16,
  },
  footerText: { color: "#666", fontSize: 14 },
  link: { color: "#0B6623", fontWeight: "600", fontSize: 14 },
});