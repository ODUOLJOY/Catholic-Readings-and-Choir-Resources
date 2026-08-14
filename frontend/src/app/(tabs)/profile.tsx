import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { router } from "expo-router";
import {
  Ionicons,
  MaterialCommunityIcons,
  FontAwesome5,
} from "@expo/vector-icons";

const API_URL =
  "https://catholic-readings-and-choir-resource-app.onrender.com";

interface User {
  id?: number;
  username?: string;
  email?: string;
  full_name?: string;
  role?: string;
  parish_id?: number;
}

export default function Profile() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadProfile();
  }, []);

  async function loadProfile() {
    try {
      const token =
        await AsyncStorage.getItem("access_token");

      const savedUser =
        await AsyncStorage.getItem("user");

      if (savedUser) {
        setUser(JSON.parse(savedUser));
      }

      if (!token) {
        setLoading(false);
        return;
      }

      try {
        const response = await fetch(
          `${API_URL}/api/auth/me`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );

        if (response.ok) {
          const data = await response.json();

          setUser(data);

          await AsyncStorage.setItem(
            "user",
            JSON.stringify(data)
          );
        }
      } catch {
        // Keep locally saved user if API is unavailable.
      }
    } catch {
      Alert.alert(
        "Error",
        "Unable to load your profile."
      );
    } finally {
      setLoading(false);
    }
  }

  async function logout() {
    Alert.alert(
      "Log Out",
      "Are you sure you want to log out?",
      [
        {
          text: "Cancel",
          style: "cancel",
        },
        {
          text: "Log Out",
          style: "destructive",
          onPress: async () => {
            try {
              await AsyncStorage.multiRemove([
                "access_token",
                "refresh_token",
                "user",
              ]);

              router.replace("/login");
            } catch {
              Alert.alert(
                "Error",
                "Unable to log out."
              );
            }
          },
        },
      ]
    );
  }

  function openSettings() {
    Alert.alert(
      "Settings",
      "Settings will be available here."
    );
  }

  if (loading) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator
          size="large"
          color="#0B6623"
        />

        <Text style={styles.loadingText}>
          Loading profile...
        </Text>
      </View>
    );
  }

  const displayName =
    user?.full_name ||
    user?.username ||
    "Catholic User";

  const email =
    user?.email ||
    "No email available";

  const role =
    user?.role || "User";

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      {/* HEADER */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>
          Profile
        </Text>

        <Pressable
          style={styles.settingsButton}
          onPress={openSettings}
        >
          <Ionicons
            name="settings-outline"
            size={23}
            color="#0B6623"
          />
        </Pressable>
      </View>

      {/* PROFILE CARD */}
      <View style={styles.profileCard}>
        <View style={styles.avatar}>
          <FontAwesome5
            name="user"
            size={35}
            color="#fff"
          />
        </View>

        <Text style={styles.name}>
          {displayName}
        </Text>

        <Text style={styles.email}>
          {email}
        </Text>

        <View style={styles.roleBadge}>
          <Text style={styles.roleText}>
            {role.toUpperCase()}
          </Text>
        </View>
      </View>

      {/* ACCOUNT */}
      <Text style={styles.sectionTitle}>
        Account
      </Text>

      <View style={styles.section}>
        <ProfileRow
          icon={
            <Ionicons
              name="person-outline"
              size={22}
              color="#0B6623"
            />
          }
          title="User Account"
          subtitle="Manage your account information"
          onPress={() =>
            Alert.alert(
              "User Account",
              `Name: ${displayName}\nEmail: ${email}`
            )
          }
        />

        <ProfileRow
          icon={
            <Ionicons
              name="settings-outline"
              size={22}
              color="#0B6623"
            />
          }
          title="Settings"
          subtitle="App preferences and configuration"
          onPress={openSettings}
        />

        <ProfileRow
          icon={
            <MaterialCommunityIcons
              name="bell-outline"
              size={23}
              color="#0B6623"
            />
          }
          title="Notifications"
          subtitle="Manage reading and choir notifications"
          onPress={() =>
            Alert.alert(
              "Notifications",
              "Notification settings will be available here."
            )
          }
        />

        <ProfileRow
          icon={
            <MaterialCommunityIcons
              name="church"
              size={23}
              color="#0B6623"
            />
          }
          title="My Parish"
          subtitle={
            user?.parish_id
              ? `Parish ID: ${user.parish_id}`
              : "No parish selected"
          }
          onPress={() =>
            Alert.alert(
              "My Parish",
              "Parish management will be available here."
            )
          }
        />
      </View>

      {/* APP */}
      <Text style={styles.sectionTitle}>
        Catholic Resources
      </Text>

      <View style={styles.section}>
        <ProfileRow
          icon={
            <MaterialCommunityIcons
              name="book-open-page-variant"
              size={23}
              color="#0B6623"
            />
          }
          title="Daily Readings"
          subtitle="View today's Catholic readings"
          onPress={() =>
            router.push("/readings")
          }
        />

        <ProfileRow
          icon={
            <MaterialCommunityIcons
              name="music-box-multiple"
              size={23}
              color="#0B6623"
            />
          }
          title="Choir Resources"
          subtitle="Browse Catholic choir songs"
          onPress={() =>
            router.push("/choir")
          }
        />

        <ProfileRow
          icon={
            <Ionicons
              name="download-outline"
              size={23}
              color="#0B6623"
            />
          }
          title="Downloads"
          subtitle="Access saved resources offline"
          onPress={() =>
            router.push("/downloads")
          }
        />
      </View>

      {/* LOGOUT */}
      <Pressable
        style={styles.logoutButton}
        onPress={logout}
      >
        <Ionicons
          name="log-out-outline"
          size={22}
          color="#C62828"
        />

        <Text style={styles.logoutText}>
          Log Out
        </Text>
      </Pressable>

      <Text style={styles.version}>
        Catholic Readings & Choir Resources
      </Text>
    </ScrollView>
  );
}

interface ProfileRowProps {
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  onPress: () => void;
}

function ProfileRow({
  icon,
  title,
  subtitle,
  onPress,
}: ProfileRowProps) {
  return (
    <Pressable
      style={styles.row}
      onPress={onPress}
    >
      <View style={styles.rowIcon}>
        {icon}
      </View>

      <View style={styles.rowContent}>
        <Text style={styles.rowTitle}>
          {title}
        </Text>

        <Text style={styles.rowSubtitle}>
          {subtitle}
        </Text>
      </View>

      <Ionicons
        name="chevron-forward"
        size={20}
        color="#999"
      />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F7F9F7",
  },

  content: {
    padding: 20,
    paddingBottom: 40,
  },

  loading: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#fff",
  },

  loadingText: {
    marginTop: 10,
    color: "#666",
  },

  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 20,
  },

  headerTitle: {
    fontSize: 29,
    fontWeight: "800",
    color: "#0B6623",
  },

  settingsButton: {
    width: 45,
    height: 45,
    borderRadius: 23,
    backgroundColor: "#EAF4ED",
    alignItems: "center",
    justifyContent: "center",
  },

  profileCard: {
    backgroundColor: "#0B6623",
    borderRadius: 20,
    padding: 25,
    alignItems: "center",
    marginBottom: 25,
  },

  avatar: {
    width: 78,
    height: 78,
    borderRadius: 39,
    backgroundColor: "#175F2D",
    justifyContent: "center",
    alignItems: "center",
    marginBottom: 12,
  },

  name: {
    color: "#fff",
    fontSize: 23,
    fontWeight: "800",
  },

  email: {
    color: "#D9EBDD",
    fontSize: 14,
    marginTop: 5,
  },

  roleBadge: {
    backgroundColor: "#fff",
    paddingHorizontal: 13,
    paddingVertical: 6,
    borderRadius: 20,
    marginTop: 12,
  },

  roleText: {
    color: "#0B6623",
    fontSize: 11,
    fontWeight: "800",
  },

  sectionTitle: {
    fontSize: 20,
    fontWeight: "800",
    color: "#222",
    marginBottom: 10,
  },

  section: {
    backgroundColor: "#fff",
    borderRadius: 15,
    marginBottom: 24,
    overflow: "hidden",
  },

  row: {
    flexDirection: "row",
    alignItems: "center",
    padding: 15,
    borderBottomWidth: 1,
    borderBottomColor: "#eee",
  },

  rowIcon: {
    width: 43,
    height: 43,
    borderRadius: 22,
    backgroundColor: "#EAF4ED",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },

  rowContent: {
    flex: 1,
  },

  rowTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#222",
  },

  rowSubtitle: {
    fontSize: 12,
    color: "#777",
    marginTop: 3,
  },

  logoutButton: {
    backgroundColor: "#FDECEC",
    borderRadius: 12,
    padding: 15,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    marginBottom: 20,
  },

  logoutText: {
    color: "#C62828",
    fontSize: 16,
    fontWeight: "700",
  },

  version: {
    textAlign: "center",
    color: "#999",
    fontSize: 12,
  },
});