import { useEffect, useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from "react-native";
import { router } from "expo-router";
import { authService } from "@/services/authService";
import { googleAuthService } from "@/services/googleAuthService";

export default function LoginScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [googleEnabled, setGoogleEnabled] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  useEffect(() => {
    let active = true;
    googleAuthService.isEnabled().then((enabled) => {
      if (active) setGoogleEnabled(enabled);
    });
    return () => {
      active = false;
    };
  }, []);

  const routeAfterAuth = async () => {
    const user = await authService.getUser();
    const role = await authService.getRole();

    if (role === "admin" || role === "super_admin" || role === "superadmin") {
      router.replace("/(tabs)/admin/dashboard");
    } else if (user && user.profile_setup_completed) {
      router.replace("/(tabs)");
    } else {
      router.replace("/profile-setup");
    }
  };

  const login = async () => {
    if (!email.trim() || !password.trim()) {
      Alert.alert("Missing Information", "Please enter your email and password.");
      return;
    }

    try {
      setLoading(true);
      await authService.login(email, password);
      await routeAfterAuth();
    } catch (error: any) {
      let message = "Unable to login.";
      if (error.response?.data?.detail) {
        message = error.response.data.detail;
      }
      Alert.alert("Login Failed", message);
    } finally {
      setLoading(false);
    }
  };

  const signInWithGoogle = async () => {
    try {
      setGoogleLoading(true);
      await googleAuthService.signIn();
      await routeAfterAuth();
    } catch (error: any) {
      const message =
        error?.response?.data?.detail ||
        error?.message ||
        "Unable to sign in with Google.";
      Alert.alert("Google Sign-In Failed", message);
    } finally {
      setGoogleLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView
        contentContainerStyle={styles.container}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.title}>
          Catholic Readings
        </Text>

        <Text style={styles.subtitle}>
          & Choir Resources
        </Text>

        <TextInput
          placeholder="Email Address"
          keyboardType="email-address"
          autoCapitalize="none"
          autoCorrect={false}
          value={email}
          onChangeText={setEmail}
          style={styles.input}
        />

        <TextInput
          placeholder="Password"
          secureTextEntry
          autoCapitalize="none"
          value={password}
          onChangeText={setPassword}
          style={styles.input}
        />

        <TouchableOpacity
          style={styles.loginButton}
          disabled={loading}
          onPress={login}
        >
          {loading ? (
            <ActivityIndicator color="#ffffff" />
          ) : (
            <Text style={styles.loginText}>
              Login
            </Text>
          )}
        </TouchableOpacity>

        {googleEnabled && (
          <>
            <View style={styles.dividerRow}>
              <View style={styles.dividerLine} />
              <Text style={styles.dividerText}>or</Text>
              <View style={styles.dividerLine} />
            </View>

            <TouchableOpacity
              style={styles.googleButton}
              disabled={loading || googleLoading}
              onPress={signInWithGoogle}
            >
              {googleLoading ? (
                <ActivityIndicator color="#0B6623" />
              ) : (
                <Text style={styles.googleText}>Continue with Google</Text>
              )}
            </TouchableOpacity>
          </>
        )}

        <TouchableOpacity
          onPress={() => router.push("/forgot-password")}
        >
          <Text style={styles.link}>
            Forgot Password?
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          onPress={() => router.push("/register")}
        >
          <Text style={styles.link}>
            Don&apos;t have an account? Register
          </Text>
        </TouchableOpacity>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flexGrow: 1,
    justifyContent: "center",
    padding: 24,
    backgroundColor: "#ffffff",
  },

  title: {
    fontSize: 32,
    fontWeight: "700",
    color: "#0B6623",
    textAlign: "center",
  },

  subtitle: {
    fontSize: 18,
    color: "#555",
    textAlign: "center",
    marginBottom: 40,
  },

  input: {
    borderWidth: 1,
    borderColor: "#dcdcdc",
    borderRadius: 12,
    paddingHorizontal: 15,
    paddingVertical: 14,
    marginBottom: 16,
    fontSize: 16,
    backgroundColor: "#fff",
  },

  loginButton: {
    backgroundColor: "#0B6623",
    paddingVertical: 15,
    borderRadius: 12,
    alignItems: "center",
    marginTop: 10,
  },

  loginText: {
    color: "#fff",
    fontSize: 17,
    fontWeight: "700",
  },

  dividerRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 22,
    marginBottom: 4,
  },

  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: "#e0e0e0",
  },

  dividerText: {
    marginHorizontal: 12,
    color: "#888",
    fontSize: 13,
  },

  googleButton: {
    marginTop: 12,
    paddingVertical: 15,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#0B6623",
    alignItems: "center",
    backgroundColor: "#fff",
  },

  googleText: {
    color: "#0B6623",
    fontSize: 16,
    fontWeight: "700",
  },

  link: {
    marginTop: 20,
    textAlign: "center",
    color: "#0B6623",
    fontSize: 15,
    fontWeight: "600",
  },
});