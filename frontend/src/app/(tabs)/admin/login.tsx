import { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { router } from "expo-router";
import AsyncStorage from "@react-native-async-storage/async-storage";
import {
  Ionicons,
  MaterialCommunityIcons,
} from "@expo/vector-icons";
import { api } from "@/lib/api";

export default function AdminLogin() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] =
    useState(false);
  const [loading, setLoading] = useState(false);

  async function login() {
    const normalizedEmail =
      email.trim().toLowerCase();

    if (!normalizedEmail || !password) {
      Alert.alert(
        "Missing Information",
        "Enter your administrator email and password."
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
          "No access token returned by the server."
        );
      }

      await AsyncStorage.setItem(
        "access_token",
        access_token
      );

      const userResponse = await api.get("/api/auth/me");
      const user = userResponse.data;
      const role = String(user?.role ?? "").toLowerCase();

      if (
        role !== "admin" &&
        role !== "super_admin" &&
        role !== "superadmin"
      ) {
        Alert.alert(
          "Access Denied",
          "This account does not have administrator privileges."
        );
        return;
      }

      if (refresh_token) {
        await AsyncStorage.setItem(
          "refresh_token",
          refresh_token
        );
      }

      if (user) {
        await AsyncStorage.setItem(
          "user",
          JSON.stringify(user)
        );
      }

      await AsyncStorage.setItem(
        "user_role",
        role
      );

      router.replace(
        "/(tabs)/admin/dashboard"
      );
    } catch (error: any) {
      console.log(
        "Admin login error:",
        error?.response?.data || error
      );

      let message =
        "Unable to sign in as administrator.";

      if (error?.response?.data?.detail) {
        if (
          Array.isArray(
            error.response.data.detail
          )
        ) {
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
      } else if (!error?.response) {
        message =
          "Cannot connect to the server. Check your internet connection.";
      }

      Alert.alert(
        "Admin Login Failed",
        message
      );

    } finally {
      setLoading(false);
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
            onChangeText={setEmail}
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
            onChangeText={setPassword}
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

        <Pressable
          style={styles.backButton}
          onPress={() =>
            router.replace("/(auth)/login")
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