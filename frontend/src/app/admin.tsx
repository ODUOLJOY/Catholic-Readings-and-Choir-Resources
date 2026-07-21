import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Alert,
  ActivityIndicator,
} from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import axios from "axios";
import { router } from "expo-router";

const API_URL =
  "https://catholic-readings-and-choir-resource-app.onrender.com";

export default function AdminScreen() {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<any>(null);

  useEffect(() => {
    loadProfile();
  }, []);

  async function loadProfile() {
    try {
      const token = await AsyncStorage.getItem("access_token");

      if (!token) {
        router.replace("/(auth)/login");
        return;
      }

      const res = await axios.get(`${API_URL}/api/auth/me`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      const profile = res.data;

      if (
        profile.role !== "admin" &&
        profile.role !== "super_admin"
      ) {
        Alert.alert(
          "Access Denied",
          "You are not authorized to access the Admin Dashboard."
        );

        router.replace("/(tabs)");
        return;
      }

      setUser(profile);
    } catch (err) {
      await AsyncStorage.removeItem("access_token");
      await AsyncStorage.removeItem("refresh_token");

      router.replace("/(auth)/login");
    } finally {
      setLoading(false);
    }
  }

  async function logout() {
    await AsyncStorage.removeItem("access_token");
    await AsyncStorage.removeItem("refresh_token");

    delete axios.defaults.headers.common["Authorization"];

    router.replace("/(auth)/login");
  }

  if (loading) {
    return (
      <View style={styles.loader}>
        <ActivityIndicator size="large" color="#0B6623" />
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={{ paddingBottom: 40 }}
    >
      <Text style={styles.title}>
        Catholic Readings & Choir Resources
      </Text>

      <Text style={styles.subtitle}>
        Admin Dashboard
      </Text>

      {user && (
        <View style={styles.profile}>
          <Text style={styles.profileText}>
            {user.full_name}
          </Text>

          <Text style={styles.profileRole}>
            {user.role.toUpperCase()}
          </Text>
        </View>
      )}

      <TouchableOpacity
        style={styles.card}
        onPress={() => router.push("/admin/upload")}
      >
        <Text style={styles.cardTitle}>
          Upload Readings
        </Text>

        <Text style={styles.cardText}>
          Upload Daily Readings, Choir Files, PDFs,
          Audio and Videos.
        </Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.card}
        onPress={() => router.push("/admin/approve")}
      >
        <Text style={styles.cardTitle}>
          Approve Uploads
        </Text>

        <Text style={styles.cardText}>
          Review user submitted resources.
        </Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.card}
        onPress={() => router.push("/admin/readings")}
      >
        <Text style={styles.cardTitle}>
          Manage Readings
        </Text>

        <Text style={styles.cardText}>
          Edit or delete daily Catholic readings.
        </Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.card}
        onPress={() => router.push("/admin/saints")}
      >
        <Text style={styles.cardTitle}>
          Saints of the Day
        </Text>

        <Text style={styles.cardText}>
          Manage saints and feast days.
        </Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.card}
        onPress={() => Alert.alert("Coming Soon")}
      >
        <Text style={styles.cardTitle}>
          Manage Users
        </Text>

        <Text style={styles.cardText}>
          View users, roles and permissions.
        </Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.card}
        onPress={() => Alert.alert("Coming Soon")}
      >
        <Text style={styles.cardTitle}>
          Reports
        </Text>

        <Text style={styles.cardText}>
          View user reports and moderation queue.
        </Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.card}
        onPress={() => Alert.alert("Coming Soon")}
      >
        <Text style={styles.cardTitle}>
          Analytics
        </Text>

        <Text style={styles.cardText}>
          Application usage statistics.
        </Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.logout}
        onPress={logout}
      >
        <Text style={styles.logoutText}>
          Logout
        </Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  loader: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },

  container: {
    flex: 1,
    backgroundColor: "#F5F5F5",
    padding: 20,
  },

  title: {
    fontSize: 26,
    fontWeight: "700",
    color: "#0B6623",
    textAlign: "center",
    marginTop: 15,
  },

  subtitle: {
    fontSize: 18,
    color: "#666",
    textAlign: "center",
    marginBottom: 25,
  },

  profile: {
    backgroundColor: "#fff",
    padding: 18,
    borderRadius: 12,
    marginBottom: 20,
    elevation: 2,
  },

  profileText: {
    fontSize: 18,
    fontWeight: "700",
  },

  profileRole: {
    marginTop: 6,
    color: "#0B6623",
    fontWeight: "700",
  },

  card: {
    backgroundColor: "#fff",
    padding: 18,
    borderRadius: 12,
    marginBottom: 15,
    elevation: 2,
  },

  cardTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: "#0B6623",
  },

  cardText: {
    marginTop: 8,
    color: "#666",
    fontSize: 15,
  },

  logout: {
    backgroundColor: "#B22222",
    padding: 16,
    borderRadius: 12,
    marginTop: 25,
  },

  logoutText: {
    color: "#fff",
    fontWeight: "700",
    textAlign: "center",
    fontSize: 17,
  },
});