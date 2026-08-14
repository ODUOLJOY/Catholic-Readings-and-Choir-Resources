import { useState } from "react";
import {
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
import axios from "axios";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

const API_URL =
  "https://catholic-readings-and-choir-resource-app.onrender.com";

export default function ForgotPasswordScreen() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  async function handleRequestReset() {
    if (!email) {
      Alert.alert("Error", "Email is required");
      return;
    }

    setLoading(true);

    try {
      await axios.post(
        `${API_URL}/api/auth/forgot-password`,
        { email },
        { timeout: 15000 }
      );

      setSent(true);
      Alert.alert(
        "Success",
        "Password reset instructions sent to your email"
      );
    } catch (error: any) {
      let message =
        error?.response?.data?.detail ||
        "Failed to send reset email";

      if (error?.code === "ECONNABORTED") {
        message =
          "The server took too long to respond.";
      } else if (!error?.response) {
        message =
          "Could not connect to the server.";
      }

      Alert.alert("Error", message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.screen}
      behavior={
        Platform.OS === "ios" ? "padding" : undefined
      }
    >
      <ScrollView
        contentContainerStyle={styles.container}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.header}>
          <Pressable
            onPress={() => router.back()}
            style={styles.backButton}
          >
            <Ionicons
              name="arrow-back"
              size={24}
              color="#0B6623"
            />
          </Pressable>
          <Text style={styles.title}>Reset Password</Text>
        </View>

        <View style={styles.formCard}>
          <Text style={styles.subtitle}>
            {sent
              ? "Check your email for reset instructions"
              : "Enter your email address to receive password reset instructions"}
          </Text>

          {!sent && (
            <>
              <Text style={styles.label}>
                Email Address
              </Text>
              <View style={styles.inputWrapper}>
                <Ionicons
                  name="mail-outline"
                  size={20}
                  color="#777"
                />
                <TextInput
                  style={styles.input}
                  placeholder="Enter your email"
                  value={email}
                  onChangeText={setEmail}
                  keyboardType="email-address"
                  editable={!loading}
                />
              </View>

              <Pressable
                style={styles.button}
                onPress={handleRequestReset}
                disabled={loading}
              >
                <Text style={styles.buttonText}>
                  {loading
                    ? "Sending..."
                    : "Send Reset Instructions"}
                </Text>
              </Pressable>
            </>
          )}

          <View style={styles.footer}>
            <Text style={styles.footerText}>
              Remember your password?{" "}
            </Text>
            <Pressable
              onPress={() => router.back()}
            >
              <Text style={styles.link}>Go Back</Text>
            </Pressable>
          </View>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create<any>({
  screen: {
    flex: 1,
    backgroundColor: "#F7F9F7",
  },

  container: {
    padding: 20,
    paddingTop: 40,
  },

  header: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 30,
  },

  backButton: {
    padding: 10,
    marginRight: 10,
  },

  title: {
    fontSize: 24,
    fontWeight: "800",
    color: "#0B6623",
    flex: 1,
  },

  formCard: {
    backgroundColor: "#fff",
    borderRadius: 20,
    padding: 20,
    marginBottom: 20,
  },

  subtitle: {
    fontSize: 14,
    color: "#666",
    marginBottom: 20,
    lineHeight: 21,
  },

  label: {
    fontSize: 14,
    fontWeight: "600",
    color: "#222",
    marginBottom: 8,
  },

  inputWrapper: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#E5EAE6",
    paddingHorizontal: 12,
    backgroundColor: "#F9FAFB",
    marginBottom: 24,
  },

  input: {
    flex: 1,
    paddingVertical: 12,
    paddingHorizontal: 12,
    fontSize: 16,
    color: "#222",
  },

  button: {
    backgroundColor: "#0B6623",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
  },

  buttonText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "700",
  },

  footer: {
    flexDirection: "row",
    justifyContent: "center",
    marginTop: 20,
  },

  footerText: {
    color: "#666",
    fontSize: 14,
  },

  link: {
    color: "#0B6623",
    fontWeight: "600",
    fontSize: 14,
  },
});
