import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { api } from "@/lib/api";
import { requestErrorMessage } from "@/lib/requestFailure";

type Status = "verifying" | "success" | "error";

export default function VerifyEmailScreen() {
  const params = useLocalSearchParams<{ token?: string }>();
  const token = Array.isArray(params.token) ? params.token[0] : params.token;

  const [status, setStatus] = useState<Status>("verifying");
  const [message, setMessage] = useState("Verifying your email address...");

  useEffect(() => {
    let active = true;

    async function verify() {
      if (!token) {
        setStatus("error");
        setMessage("This verification link is missing its token.");
        return;
      }

      try {
        const response = await api.post("/api/auth/verify-email", null, {
          params: { token },
        });
        if (!active) return;
        setStatus("success");
        setMessage(
          response.data?.message ?? "Your email has been verified.",
        );
      } catch (error: any) {
        if (!active) return;
        setStatus("error");
        setMessage(
          requestErrorMessage(
            error,
            "This verification link is invalid or has already been used."
          ),
        );
      }
    }

    void verify();
    return () => {
      active = false;
    };
  }, [token]);

  return (
    <View style={styles.container}>
      {status === "verifying" ? (
        <ActivityIndicator size="large" color="#0B6623" />
      ) : null}

      <Text
        style={[
          styles.title,
          status === "error" && styles.errorTitle,
        ]}
      >
        {status === "success"
          ? "Email Verified"
          : status === "error"
            ? "Verification Failed"
            : "One Moment"}
      </Text>

      <Text style={styles.message}>{message}</Text>

      <TouchableOpacity
        style={styles.button}
        onPress={() => router.replace("/(auth)/login")}
        disabled={status === "verifying"}
      >
        <Text style={styles.buttonText}>Go to Login</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 28,
    backgroundColor: "#ffffff",
  },

  title: {
    marginTop: 22,
    fontSize: 24,
    fontWeight: "800",
    color: "#0B6623",
    textAlign: "center",
  },

  errorTitle: {
    color: "#B00020",
  },

  message: {
    marginTop: 12,
    fontSize: 15,
    color: "#555",
    textAlign: "center",
  },

  button: {
    marginTop: 28,
    backgroundColor: "#0B6623",
    paddingVertical: 14,
    paddingHorizontal: 28,
    borderRadius: 12,
  },

  buttonText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "700",
  },
});
