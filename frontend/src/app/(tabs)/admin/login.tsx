import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { router } from "expo-router";
import {
  Ionicons,
  MaterialCommunityIcons,
} from "@expo/vector-icons";
import { authService } from "@/services/authService";
import { googleAuthService } from "@/services/googleAuthService";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function AdminLogin() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
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

  async function login() {
    const trimmedEmail = email.trim().toLowerCase();

    if (!trimmedEmail || !password) {
      setError("Enter your administrator email and password.");
      return;
    }

    if (!EMAIL_REGEX.test(trimmedEmail)) {
      setError("Please enter a valid email address.");
      return;
    }

    setError(null);
    setLoading(true);

    try {
      await authService.login(trimmedEmail, password);

      const role = await authService.getRole();
      if (
        role !== "admin" &&
        role !== "super_admin" &&
        role !== "superadmin"
      ) {
        await authService.logout();
        setError(
          "This account does not have administrator privileges."
        );
        return;
      }

      router.replace("/(tabs)/admin/dashboard");
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      setError(detail || "Unable to login.");
    } finally {
      setLoading(false);
    }
  }

  async function loginWithGoogle() {
    setError(null);
    setGoogleLoading(true);
    try {
      await googleAuthService.signIn();

      const role = await authService.getRole();
      if (
        role !== "admin" &&
        role !== "super_admin" &&
        role !== "superadmin"
      ) {
        await authService.logout();
        setError(
          "This account does not have administrator privileges."
        );
        return;
      }

      router.replace("/(tabs)/admin/dashboard");
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      setError(detail || "Unable to sign in with Google.");
    } finally {
      setGoogleLoading(false);
    }
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View style={styles.logo}>
          <MaterialCommunityIcons
            name="shield-account"
            size={38}
            color="#fff"
          />
        </View>
        <Text style={styles.title}>
          Admin Login
        </Text>

        <Text style={styles.subtitle}>
          Catholic Readings & Choir Resources
        </Text>
      </View>

      <View style={styles.form}>
        {error ? <Text style={styles.errorText}>{error}</Text> : null}

        <Text style={styles.label}>
          Administrator Email
        </Text>

        <View style={styles.inputWrapper}>
          <Ionicons
            name="mail-outline"
            size={21}
            color="#777"
          />

          <TextInput
            style={styles.input}
            placeholder="Admin email"
            placeholderTextColor="#999"
            keyboardType="email-address"
            autoCapitalize="none"
            autoCorrect={false}
            autoComplete="email"
            textContentType="emailAddress"
            value={email}
            onChangeText={(value) => {
              setEmail(value);
              if (error) setError(null);
            }}
            editable={!loading}
          />
        </View>

        <Text style={styles.label}>
          Administrator Password
        </Text>

        <View style={styles.inputWrapper}>
          <Ionicons
            name="lock-closed-outline"
            size={21}
            color="#777"
          />

          <TextInput
            style={styles.input}
            placeholder="Admin password"
            placeholderTextColor="#999"
            secureTextEntry={!showPassword}
            autoCapitalize="none"
            autoCorrect={false}
            value={password}
            onChangeText={(value) => {
              setPassword(value);
              if (error) setError(null);
            }}
            editable={!loading}
            onSubmitEditing={login}
          />

          <Pressable
            onPress={() =>
              setShowPassword(
                (current) => !current
              )
            }
            hitSlop={10}
          >
            <Ionicons
              name={
                showPassword
                  ? "eye-off-outline"
                  : "eye-outline"
              }
              size={21}
              color="#777"
            />
          </Pressable>
        </View>

        <Pressable
          style={[
            styles.button,
            loading && styles.disabled,
          ]}
          onPress={login}
          disabled={loading}
        >
          {loading ? (
            <View style={styles.buttonContent}>
              <ActivityIndicator color="#fff" />
              <Text style={styles.buttonText}>
                Signing in...
              </Text>
            </View>
          ) : (
            <Text style={styles.buttonText}>
              Admin Login
            </Text>
          )}
        </Pressable>

        {googleEnabled && (
          <Pressable
            style={[
              styles.googleButton,
              (loading || googleLoading) && styles.disabled,
            ]}
            onPress={loginWithGoogle}
            disabled={loading || googleLoading}
          >
            {googleLoading ? (
              <ActivityIndicator color="#0B6623" />
            ) : (
              <Text style={styles.googleText}>
                Continue with Google
              </Text>
            )}
          </Pressable>
        )}

        <Pressable
          style={styles.backButton}
          onPress={() =>
            router.replace("/login")
          }
          disabled={loading}
        >
          <Text style={styles.backText}>
            Back to User Login
          </Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    backgroundColor: "#F7F9F7",
    padding: 22,
  },

  header: {
    alignItems: "center",
    marginBottom: 25,
  },

  logo: {
    width: 76,
    height: 76,
    borderRadius: 23,
    backgroundColor: "#0B6623",
    justifyContent: "center",
    alignItems: "center",
    marginBottom: 15,
  },

  title: {
    fontSize: 30,
    fontWeight: "800",
    color: "#0B6623",
  },

  subtitle: {
    color: "#777",
    fontSize: 13,
    textAlign: "center",
    marginTop: 5,
  },

  form: {
    backgroundColor: "#fff",
    borderRadius: 20,
    padding: 20,
    borderWidth: 1,
    borderColor: "#E5EAE6",
  },

  errorText: {
    color: "#D32F2F",
    fontSize: 13,
    fontWeight: "600",
    marginBottom: 8,
    marginTop: -4,
    paddingHorizontal: 2,
  },

  label: {
    fontSize: 14,
    fontWeight: "700",
    color: "#333",
    marginBottom: 7,
    marginTop: 5,
  },

  inputWrapper: {
    minHeight: 54,
    borderWidth: 1,
    borderColor: "#D9DED9",
    borderRadius: 13,
    paddingHorizontal: 14,
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 15,
  },

  input: {
    flex: 1,
    marginLeft: 10,
    marginRight: 8,
    color: "#222",
    fontSize: 16,
  },

  button: {
    minHeight: 54,
    backgroundColor: "#0B6623",
    borderRadius: 13,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 10,
  },

  disabled: {
    opacity: 0.7,
  },

  buttonContent: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },

  buttonText: {
    color: "#fff",
    fontSize: 17,
    fontWeight: "800",
  },

  googleButton: {
    minHeight: 54,
    borderRadius: 13,
    borderWidth: 1,
    borderColor: "#0B6623",
    alignItems: "center",
    justifyContent: "center",
    marginTop: 12,
    backgroundColor: "#fff",
  },

  googleText: {
    color: "#0B6623",
    fontSize: 16,
    fontWeight: "800",
  },

  backButton: {
    alignItems: "center",
    marginTop: 18,
  },

  backText: {
    color: "#0B6623",
    fontSize: 15,
    fontWeight: "700",
  },
});