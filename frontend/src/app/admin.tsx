import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { router } from "expo-router";
import {
  Ionicons,
  MaterialCommunityIcons,
} from "@expo/vector-icons";
import { api } from "@/lib/api";

interface DashboardStats {
  users: number;
  admins: number;
  readings: number;
  choir_resources: number;
  pending_uploads: number;
  pending_reports: number;
}

const defaultStats: DashboardStats = {
  users: 0,
  admins: 0,
  readings: 0,
  choir_resources: 0,
  pending_uploads: 0,
  pending_reports: 0,
};

export default function AdminDashboard() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [stats, setStats] =
    useState<DashboardStats>(defaultStats);

  useEffect(() => {
    loadDashboard();
  }, []);

  async function loadDashboard(
    showLoading = true
  ) {
    try {
      if (showLoading) {
        setLoading(true);
      }

      const token =
        await AsyncStorage.getItem("access_token");

      if (!token) {
        router.replace("/(auth)/login");
        return;
      }

      const response = await api.get(
        "/api/admin/dashboard",
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
          timeout: 15000,
        }
      );

      setStats({
        users: response.data?.users ?? 0,
        admins: response.data?.admins ?? 0,
        readings: response.data?.readings ?? 0,
        choir_resources:
          response.data?.choir_resources ?? 0,
        pending_uploads:
          response.data?.pending_uploads ?? 0,
        pending_reports:
          response.data?.pending_reports ?? 0,
      });
    } catch (error: any) {
      console.log(
        "Admin dashboard error:",
        error?.response?.data || error
      );

      if (
        error?.response?.status === 401 ||
        error?.response?.status === 403
      ) {
        Alert.alert(
          "Access Denied",
          "Administrator privileges are required."
        );

        router.replace("/(tabs)");
        return;
      }

      Alert.alert(
        "Error",
        "Unable to load the admin dashboard."
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  async function refresh() {
    setRefreshing(true);
    await loadDashboard(false);
  }

  async function logout() {
    await AsyncStorage.multiRemove([
      "access_token",
      "refresh_token",
      "user",
    ]);

    router.replace("/(auth)/login");
  }

  function navigate(path: string) {
    router.push(path as any);
  }

  if (loading) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator
          size="large"
          color="#0B6623"
        />

        <Text style={styles.loadingText}>
          Loading admin dashboard...
        </Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={refresh}
          colors={["#0B6623"]}
        />
      }
    >
      {/* HEADER */}
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>
            Admin Dashboard
          </Text>

          <Text style={styles.subtitle}>
            Catholic Readings & Choir Resources
          </Text>
        </View>

        <TouchableOpacity
          style={styles.refreshButton}
          onPress={refresh}
        >
          <Ionicons
            name="refresh"
            size={22}
            color="#0B6623"
          />
        </TouchableOpacity>
      </View>

      {/* OVERVIEW */}
      <Text style={styles.sectionTitle}>
        Overview
      </Text>

      <View style={styles.statsContainer}>
        <StatCard
          icon="account-group"
          number={stats.users}
          label="Total Users"
        />

        <StatCard
          icon="shield-account"
          number={stats.admins}
          label="Admins"
        />

        <StatCard
          icon="book-open-page-variant"
          number={stats.readings}
          label="Readings"
        />

        <StatCard
          icon="music-note-multiple"
          number={stats.choir_resources}
          label="Choir Resources"
        />

        <StatCard
          icon="cloud-upload"
          number={stats.pending_uploads}
          label="Pending Uploads"
          warning
        />

        <StatCard
          icon="flag"
          number={stats.pending_reports}
          label="Reports"
          warning
        />
      </View>

      {/* CONTENT MANAGEMENT */}
      <Text style={styles.sectionTitle}>
        Content Management
      </Text>

      <AdminButton
        icon="cloud-upload-outline"
        title="Upload Choir Resource"
        description="Add songs, hymns, scores and audio"
        onPress={() =>
          navigate("/(tabs)/admin/upload")
        }
      />

      <AdminButton
        icon="book-outline"
        title="Manage Readings"
        description="Manage daily Catholic readings"
        onPress={() =>
          navigate("/(tabs)/admin/readings")
        }
      />

      <AdminButton
        icon="checkmark-done-outline"
        title="Approve Uploads"
        description="Review pending resources"
        badge={
          stats.pending_uploads > 0
            ? stats.pending_uploads
            : undefined
        }
        onPress={() =>
          navigate("/(tabs)/admin/approve")
        }
      />

      <AdminButton
        icon="person-outline"
        title="Manage Users"
        description="View and manage user accounts"
        onPress={() =>
          navigate("/(tabs)/admin/users")
        }
      />

      <AdminButton
        icon="people-outline"
        title="Manage Parishes"
        description="Manage parish accounts and access"
        onPress={() =>
          navigate("/(tabs)/admin/parishes")
        }
      />

      {/* LITURGICAL DATA */}
      <Text style={styles.sectionTitle}>
        Liturgical Data
      </Text>

      <AdminButton
        icon="person-circle-outline"
        title="Saints Database"
        description="Manage saints and feast days"
        onPress={() =>
          navigate("/(tabs)/admin/saints")
        }
      />

      <AdminButton
        icon="calendar-outline"
        title="Liturgical Calendar"
        description="Manage Catholic calendar data"
        onPress={() =>
          navigate("/(tabs)/admin/calendar")
        }
      />

      <AdminButton
        icon="musical-notes-outline"
        title="Choir Categories"
        description="Manage hymn and song categories"
        onPress={() =>
          navigate("/(tabs)/admin/choir-categories")
        }
      />

      {/* REPORTS & ANALYTICS */}
      <Text style={styles.sectionTitle}>
        Reports & Analytics
      </Text>

      <AdminButton
        icon="flag-outline"
        title="Reports"
        description="Review reported resources"
        badge={
          stats.pending_reports > 0
            ? stats.pending_reports
            : undefined
        }
        onPress={() =>
          navigate("/(tabs)/admin/reports")
        }
      />

      <AdminButton
        icon="bar-chart-outline"
        title="Analytics"
        description="View application statistics"
        onPress={() =>
          navigate("/(tabs)/admin/analytics")
        }
      />

      {/* SYSTEM */}
      <Text style={styles.sectionTitle}>
        System
      </Text>

      <AdminButton
        icon="settings-outline"
        title="Admin Settings"
        description="Configure application settings"
        onPress={() =>
          navigate("/(tabs)/admin/settings")
        }
      />

      {/* LOGOUT */}
      <TouchableOpacity
        style={styles.logout}
        onPress={logout}
      >
        <Ionicons
          name="log-out-outline"
          size={22}
          color="#fff"
        />

        <Text style={styles.logoutText}>
          Logout
        </Text>
      </TouchableOpacity>

      <Text style={styles.footer}>
        Catholic Readings & Choir Resources
      </Text>
    </ScrollView>
  );
}

/* =========================
   STAT CARD
========================= */

function StatCard({
  icon,
  number,
  label,
  warning = false,
}: {
  icon: any;
  number: number;
  label: string;
  warning?: boolean;
}) {
  return (
    <View
      style={[
        styles.statCard,
        warning &&
          number > 0 &&
          styles.warningCard,
      ]}
    >
      <View
        style={[
          styles.statIcon,
          warning &&
            number > 0 &&
            styles.warningIcon,
        ]}
      >
        <MaterialCommunityIcons
          name={icon}
          size={25}
          color={
            warning && number > 0
              ? "#C77700"
              : "#0B6623"
          }
        />
      </View>

      <Text style={styles.number}>
        {number}
      </Text>

      <Text style={styles.statLabel}>
        {label}
      </Text>
    </View>
  );
}

/* =========================
   ADMIN BUTTON
========================= */

function AdminButton({
  icon,
  title,
  description,
  badge,
  onPress,
}: {
  icon: any;
  title: string;
  description: string;
  badge?: number;
  onPress: () => void;
}) {
  return (
    <TouchableOpacity
      style={styles.adminButton}
      onPress={onPress}
      activeOpacity={0.75}
    >
      <View style={styles.adminIcon}>
        <Ionicons
          name={icon}
          size={24}
          color="#0B6623"
        />
      </View>

      <View style={styles.adminText}>
        <Text style={styles.adminTitle}>
          {title}
        </Text>

        <Text style={styles.adminDescription}>
          {description}
        </Text>
      </View>

      {badge !== undefined && (
        <View style={styles.badge}>
          <Text style={styles.badgeText}>
            {badge}
          </Text>
        </View>
      )}

      <Ionicons
        name="chevron-forward"
        size={20}
        color="#999"
      />
    </TouchableOpacity>
  );
}

/* =========================
   STYLES
========================= */

const styles = StyleSheet.create<any>({
  container: {
    flex: 1,
    backgroundColor: "#F7F9F7",
  },

  content: {
    padding: 18,
    paddingBottom: 40,
  },

  loading: {
    flex: 1,
    backgroundColor: "#fff",
    justifyContent: "center",
    alignItems: "center",
  },

  loadingText: {
    marginTop: 10,
    color: "#666",
  },

  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 25,
  },

  title: {
    fontSize: 27,
    fontWeight: "800",
    color: "#0B6623",
  },

  subtitle: {
    color: "#777",
    fontSize: 13,
    marginTop: 4,
  },

  refreshButton: {
    width: 45,
    height: 45,
    borderRadius: 23,
    backgroundColor: "#EAF4ED",
    justifyContent: "center",
    alignItems: "center",
  },

  sectionTitle: {
    fontSize: 19,
    fontWeight: "800",
    color: "#222",
    marginTop: 5,
    marginBottom: 12,
  },

  statsContainer: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    marginBottom: 22,
  },

  statCard: {
    width: "48%",
    backgroundColor: "#fff",
    borderRadius: 15,
    padding: 15,
    marginBottom: 12,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#E5EAE6",
  },

  warningCard: {
    borderColor: "#F0D9A8",
    backgroundColor: "#FFFBF3",
  },

  statIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: "#EAF4ED",
    justifyContent: "center",
    alignItems: "center",
    marginBottom: 8,
  },

  warningIcon: {
    backgroundColor: "#FFF0D2",
  },

  number: {
    fontSize: 27,
    fontWeight: "800",
    color: "#0B6623",
  },

  statLabel: {
    fontSize: 12,
    color: "#666",
    textAlign: "center",
    marginTop: 3,
  },

  adminButton: {
    backgroundColor: "#fff",
    borderRadius: 14,
    padding: 13,
    marginBottom: 10,
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#E5EAE6",
  },

  adminIcon: {
    width: 45,
    height: 45,
    borderRadius: 12,
    backgroundColor: "#EAF4ED",
    justifyContent: "center",
    alignItems: "center",
  },

  adminText: {
    flex: 1,
    marginLeft: 12,
  },

  adminTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#222",
  },

  adminDescription: {
    color: "#888",
    fontSize: 12,
    marginTop: 3,
  },

  badge: {
    minWidth: 27,
    height: 27,
    borderRadius: 14,
    backgroundColor: "#C62828",
    justifyContent: "center",
    alignItems: "center",
    marginRight: 10,
  },

  badgeText: {
    color: "#fff",
    fontWeight: "800",
    fontSize: 12,
  },

  logout: {
    marginTop: 25,
    backgroundColor: "#C62828",
    borderRadius: 13,
    padding: 15,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
  },

  logoutText: {
    color: "#fff",
    fontWeight: "800",
    fontSize: 16,
    marginLeft: 8,
  },

  footer: {
    textAlign: "center",
    color: "#999",
    fontSize: 11,
    marginTop: 20,
  },
});