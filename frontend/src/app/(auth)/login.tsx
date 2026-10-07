import { useEffect, useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from "react-native";
import { router } from "expo-router";
import { requestErrorMessage } from "@/lib/requestFailure";
import { authService } from "@/services/authService";
import { googleAuthService } from "@/services/googleAuthService";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function LoginScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [googleEnabled, setGoogleEnabled] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  const validate = (): boolean => {
    if (!email.trim()) {
      setError("Please enter your email address.");
      return false;
    }
    if (!EMAIL_REGEX.test(email.trim().toLowerCase())) {
      setError("Please enter a valid email address.");
      return false;
    }
    if (!password) {
      setError("Please enter your password.");
      return false;
    }
    if (password.length < 6) {
      setError("Password must be at least 6 characters.");
      return false;
    }
    setError(null);
    return true;
  };

  const login = async () => {
    if (!validate()) {
      return;
    }

    setLoading(true);

    try {
      await authService.login(email, password);
      await routeAfterAuth();
    } catch (error: any) {
      setError(requestErrorMessage(error, "Invalid email or password."));
    } finally {
      setLoading(false);
    }
  };

  const signInWithGoogle = async () => {
    setGoogleLoading(true);
    setError(null);

    try {
      await googleAuthService.signIn();
      await routeAfterAuth();
    } catch (error: any) {
      setError(requestErrorMessage(error, "Unable to sign in with Google."));
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
          &amp; Choir Resources
        </Text>

        <TextInput
          placeholder="Email Address"
          keyboardType="email-address"
          autoCapitalize="none"
          autoCorrect={false}
          value={email}
          onChangeText={(value) => {
            setEmail(value);
            if (error) setError(null);
          }}
          style={styles.input}
          editable={!loading}
          placeholderTextColor="#999"
        />

        <TextInput
          placeholder="Password"
          secureTextEntry
          autoCapitalize="none"
          value={password}
          onChangeText={(value) => {
            setPassword(value);
            if (error) setError(null);
          }}
          style={styles.input}
          editable={!loading}
          placeholderTextColor="#999"
        />

        {error ? <Text style={styles.errorText}>{error}</Text> : null}

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
          disabled={loading}
        >
          <Text style={styles.link}>
            Forgot Password?
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          onPress={() => router.push("/register")}
          disabled={loading}
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

  errorText: {
    color: "#D32F2F",
    fontSize: 13,
    marginBottom: 8,
    marginTop: -8,
    paddingHorizontal: 4,
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
