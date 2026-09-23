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
import AsyncStorage from "@react-native-async-storage/async-storage";
import { Ionicons, MaterialCommunityIcons } from "@expo/vector-icons";
import { api } from "@/lib/api";

export default function LoginScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  async function login() {
    const normalizedEmail = email.trim().toLowerCase();

    if (!normalizedEmail || !password) {
      Alert.alert(
        "Missing Information",
        "Please enter your email address and password."
      );
      return;
    }

    try {
      setLoading(true);

      const response = await api.post(
        "/api/auth/login",
        {
          email: normalizedEmail,
          password,
        },
        {
          headers: {
            "Content-Type": "application/json",
          },
          timeout: 20000,
        }
      );

      const { access_token, refresh_token } = response.data ?? {};

      if (!access_token) {
        throw new Error(
          "The server did not return an access token."
        );
      }

      await AsyncStorage.setItem(
        "access_token",
        access_token
      );

      const userResponse = await api.get("/api/auth/me");
      const user = userResponse.data;

      if (refresh_token) {
        await AsyncStorage.setItem(
          "refresh_token",
          refresh_token
        );
      } else {
        await AsyncStorage.removeItem(
          "refresh_token"
        );
      }

      if (user) {
        await AsyncStorage.setItem(
          "user",
          JSON.stringify(user)
        );

        if (user.role) {
          await AsyncStorage.setItem(
            "user_role",
            String(user.role)
          );
        }
      }

      router.replace("/(tabs)");
    } catch (error: any) {
      console.log(
        "Login error:",
        error?.response?.data || error
      );

      let message =
        "Unable to sign in. Please try again.";

      if (error?.response?.data?.detail) {
        if (Array.isArray(error.response.data.detail)) {
          message = error.response.data.detail
            .map((item: any) =>
              item?.msg
                ? String(item.msg)
                : String(item)
            )
            .join("\n");
        } else {
          message = String(
            error.response.data.detail
          );
        }
      } else if (
        error?.code === "ECONNABORTED"
      ) {
        message =
          "The server took too long to respond.";
      } else if (!error?.response) {
        message =
          "Could not connect to the server. Check your internet connection.";
      }

      Alert.alert("Login Failed", message);
    } finally {
      setLoading(false);
    }
  }

  function openRegister() {
    router.push("/(auth)/register" as any);
  }

  function openForgotPassword() {
    router.push("/(auth)/forgot-password" as any);
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
        <View style={styles.logoContainer}>
          <View style={styles.logo}>
            <MaterialCommunityIcons
              name="church"
              size={34}
              color="#fff"
            />
          </View>

          <Text style={styles.brand}>
            Catholic Readings
          </Text>

          <Text style={styles.brandSub}>
            & Choir Resources
          </Text>
        </View>

        <View style={styles.formCard}>
          <Text style={styles.title}>
            Welcome Back
          </Text>

          <Text style={styles.subtitle}>
            Sign in to continue
          </Text>

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
              placeholderTextColor="#999"
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
              autoComplete="email"
              textContentType="emailAddress"
              value={email}
              onChangeText={setEmail}
              editable={!loading}
              returnKeyType="next"
            />
          </View>

          <Text style={styles.label}>
            Password
          </Text>

          <View style={styles.inputWrapper}>
            <Ionicons
              name="lock-closed-outline"
              size={20}
              color="#777"
            />

            <TextInput
              style={styles.input}
              placeholder="Enter your password"
              placeholderTextColor="#999"
              secureTextEntry={!showPassword}
              autoCapitalize="none"
              autoCorrect={false}
              autoComplete="password"
              textContentType="password"
              value={password}
              onChangeText={setPassword}
              editable={!loading}
              onSubmitEditing={login}
              returnKeyType="done"
            />

            <Pressable
              onPress={() =>
                setShowPassword((value) => !value)
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
            onPress={openForgotPassword}
            style={styles.forgotButton}
          >
            <Text style={styles.forgotText}>
              Forgot Password?
            </Text>
          </Pressable>

          <Pressable
            style={[
              styles.loginButton,
              loading && styles.loginButtonDisabled,
            ]}
            onPress={login}
            disabled={loading}
          >
            {loading ? (
              <View style={styles.buttonContent}>
                <ActivityIndicator color="#fff" />
                <Text style={styles.loginText}>
                  Signing in...
                </Text>
              </View>
            ) : (
              <Text style={styles.loginText}>
                Login
              </Text>
            )}
          </Pressable>

          <View style={styles.dividerRow}>
            <View style={styles.divider} />
            <Text style={styles.dividerText}>
              OR
            </Text>
            <View style={styles.divider} />
          </View>

          <Pressable
            style={styles.registerButton}
            onPress={openRegister}
            disabled={loading}
          >
            <Text style={styles.registerText}>
              Create an Account
            </Text>
          </Pressable>
        </View>

        <Text style={styles.footer}>
          By signing in, you agree to use the app
          responsibly and respectfully.
        </Text>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: "#F7F9F7",
  },

  container: {
    flexGrow: 1,
    justifyContent: "center",
    padding: 22,
  },

  logoContainer: {
    alignItems: "center",
    marginBottom: 26,
  },

  logo: {
    width: 72,
    height: 72,
    borderRadius: 22,
    backgroundColor: "#0B6623",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 12,
  },

  brand: {
    fontSize: 25,
    fontWeight: "800",
    color: "#0B6623",
  },

  brandSub: {
    fontSize: 16,
    color: "#666",
    marginTop: 2,
  },

  formCard: {
    backgroundColor: "#fff",
    borderRadius: 20,
    padding: 20,
    borderWidth: 1,
    borderColor: "#E5EAE6",
  },

  title: {
    fontSize: 27,
    fontWeight: "800",
    color: "#222",
    textAlign: "center",
  },

  subtitle: {
    fontSize: 14,
    color: "#777",
    textAlign: "center",
    marginTop: 5,
    marginBottom: 25,
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
    backgroundColor: "#fff",
  },

  input: {
    flex: 1,
    marginLeft: 10,
    marginRight: 8,
    fontSize: 16,
    color: "#222",
    paddingVertical: 13,
  },

  forgotButton: {
    alignSelf: "flex-end",
    marginTop: 10,
    marginBottom: 5,
  },

  forgotText: {
    color: "#0B6623",
    fontWeight: "700",
    fontSize: 14,
  },

  loginButton: {
    backgroundColor: "#0B6623",
    minHeight: 54,
    borderRadius: 13,
    justifyContent: "center",
    alignItems: "center",
    marginTop: 18,
  },

  loginButtonDisabled: {
    opacity: 0.75,
  },

  buttonContent: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },

  loginText: {
    color: "#fff",
    fontSize: 17,
    fontWeight: "800",
  },

  dividerRow: {
    flexDirection: "row",
    alignItems: "center",
    marginVertical: 20,
  },

  divider: {
    flex: 1,
    height: 1,
    backgroundColor: "#E5E5E5",
  },

  dividerText: {
    marginHorizontal: 12,
    color: "#999",
    fontSize: 12,
    fontWeight: "700",
  },

  registerButton: {
    minHeight: 52,
    borderRadius: 13,
    borderWidth: 1.5,
    borderColor: "#0B6623",
    alignItems: "center",
    justifyContent: "center",
  },

  registerText: {
    color: "#0B6623",
    fontSize: 16,
    fontWeight: "800",
  },

  footer: {
    textAlign: "center",
    color: "#999",
    fontSize: 11,
    lineHeight: 17,
    marginTop: 18,
    paddingHorizontal: 10,
  },
});