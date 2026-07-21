import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import axios from "axios";
import { router } from "expo-router";

const API_URL =
  "https://catholic-readings-and-choir-resource-app.onrender.com";

interface DashboardStats {
  users: number;
  admins: number;
  readings: number;
  choir_resources: number;
  pending_uploads: number;
  pending_reports: number;
}

export default function AdminDashboard() {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<DashboardStats>({
    users: 0,
    admins: 0,
    readings: 0,
    choir_resources: 0,
    pending_uploads: 0,
    pending_reports: 0,
  });

  useEffect(() => {
    loadDashboard();
  }, []);

  async function loadDashboard() {
    try {
      const token = await AsyncStorage.getItem("access_token");

      const response = await axios.get(
        `${API_URL}/api/admin/dashboard`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      setStats(response.data);
    } catch (error) {
      Alert.alert(
        "Access Denied",
        "Administrator privileges required."
      );

      router.replace("/(tabs)");
    } finally {
      setLoading(false);
    }
  }

  async function logout() {
    await AsyncStorage.clear();
    router.replace("/(auth)/login");
  }

  if (loading) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator
          size="large"
          color="#0B6623"
        />
      </View>
    );
  }

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>
        Admin Dashboard
      </Text>

      <View style={styles.statsContainer}>
        <View style={styles.card}>
          <Text style={styles.number}>
            {stats.users}
          </Text>
          <Text>Total Users</Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.number}>
            {stats.admins}
          </Text>
          <Text>Admins</Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.number}>
            {stats.readings}
          </Text>
          <Text>Readings</Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.number}>
            {stats.choir_resources}
          </Text>
          <Text>Choir Files</Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.number}>
            {stats.pending_uploads}
          </Text>
          <Text>Pending Uploads</Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.number}>
            {stats.pending_reports}
          </Text>
          <Text>Reports</Text>
        </View>
      </View>

      <TouchableOpacity
        style={styles.button}
        onPress={() => router.push("/admin/upload")}
      >
        <Text style={styles.buttonText}>
          Upload Choir Resource
        </Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.button}
        onPress={() => router.push("/admin/readings")}
      >
        <Text style={styles.buttonText}>
          Manage Readings
        </Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.button}
        onPress={() => router.push("/admin/users")}
      >
        <Text style={styles.buttonText}>
          Manage Users
        </Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.button}
        onPress={() => router.push("/admin/approve")}
      >
        <Text style={styles.buttonText}>
          Approve Uploads
        </Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.button}
        onPress={() => router.push("/admin/reports")}
      >
        <Text style={styles.buttonText}>
          View Reports
        </Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.button}
        onPress={() => router.push("/admin/analytics")}
      >
        <Text style={styles.buttonText}>
          Analytics
        </Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.button}
        onPress={() => router.push("/admin/saints")}
      >
        <Text style={styles.buttonText}>
          Saints Database
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
  container: {
    flex: 1,
    backgroundColor: "#fff",
    padding: 20,
  },

  loading: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },

  title: {
    fontSize: 30,
    fontWeight: "bold",
    color: "#0B6623",
    marginBottom: 20,
    textAlign: "center",
  },

  statsContainer: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    marginBottom: 25,
  },

  card: {
    width: "48%",
    backgroundColor: "#F3F6F4",
    padding: 18,
    borderRadius: 12,
    marginBottom: 15,
    alignItems: "center",
    elevation: 2,
  },

  number: {
    fontSize: 28,
    fontWeight: "bold",
    color: "#0B6623",
    marginBottom: 5,
  },

  button: {
    backgroundColor: "#0B6623",
    padding: 15,
    borderRadius: 12,
    marginBottom: 12,
  },

  buttonText: {
    color: "#fff",
    fontWeight: "700",
    textAlign: "center",
    fontSize: 16,
  },

  logout: {
    backgroundColor: "#C62828",
    padding: 15,
    borderRadius: 12,
    marginTop: 30,
    marginBottom: 30,
  },

  logoutText: {
    color: "#fff",
    textAlign: "center",
    fontWeight: "700",
    fontSize: 16,
  },
});