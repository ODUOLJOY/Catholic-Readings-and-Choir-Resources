import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { useCallback, useEffect, useState, type ComponentProps } from "react";
import { router, type Href } from "expo-router";
import {
  Ionicons,
  MaterialCommunityIcons,
} from "@expo/vector-icons";
import { api } from "@/lib/api";

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [platformAdmin, setPlatformAdmin] = useState(false);
  const [roles, setRoles] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const loadAccess = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [userResponse, communityResponse] = await Promise.all([
        api.get("/api/auth/me"),
        api.get("/api/community/me"),
      ]);
      const role = String(userResponse.data?.role ?? "").toLowerCase();
      setPlatformAdmin(role === "admin" || role === "super_admin");
      setRoles(
        Array.isArray(communityResponse.data?.roles)
          ? communityResponse.data.roles.map((assignment: { role: string }) => assignment.role)
          : [],
      );
    } catch {
      setError("Unable to verify your administrative access. Check your connection and try again.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(loadAccess);
  }, [loadAccess]);

  if (loading) {
    return (
      <View style={styles.accessState}>
        <ActivityIndicator color="#0B6623" />
        <Text style={styles.accessMessage}>Checking your access…</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.accessState}>
        <Text style={styles.accessMessage}>{error}</Text>
        <TouchableOpacity style={styles.retryButton} onPress={() => void loadAccess()}>
          <Text style={styles.retryText}>Retry</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={() => router.replace("/login")}>
          <Text style={styles.backText}>Sign in</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (!platformAdmin) {
    const canManageCommunity = roles.some((role) =>
      ["parish_admin", "diocesan_admin", "moderator"].includes(role),
    );
    const canManageChoir = roles.some((role) =>
      ["parish_admin", "diocesan_admin", "parish_music_director", "choir_director"].includes(role),
    );
    if (!canManageCommunity && !canManageChoir) {
      return (
        <View style={styles.accessState}>
          <MaterialCommunityIcons name="shield-lock-outline" size={42} color="#0B6623" />
          <Text style={styles.accessTitle}>Administrative access required</Text>
          <Text style={styles.accessMessage}>
            This area is available to platform administrators and approved parish or diocesan officers.
          </Text>
          <TouchableOpacity style={styles.retryButton} onPress={() => router.replace("/(tabs)")}>
            <Text style={styles.retryText}>Return to Home</Text>
          </TouchableOpacity>
        </View>
      );
    }
    return <ScopedDashboard roles={roles} />;
  }

  function navigate(path: Href) {
    router.push(path);
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      {/* HEADER */}
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>
            Admin Dashboard
          </Text>

          <Text style={styles.subtitle}>
            Manage Catholic content and choir resources
          </Text>
        </View>

        <View style={styles.headerIcon}>
          <MaterialCommunityIcons
            name="shield-account"
            size={28}
            color="#0B6623"
          />
        </View>
      </View>

      {/* READINGS */}
      <Text style={styles.sectionTitle}>
        Readings
      </Text>

      <AdminCard
        icon="cloud-upload-outline"
        title="Create Reading Record"
        description="Enter verified daily reading text and references"
        onPress={() =>
          navigate("/(tabs)/admin/readings")
        }
      />

      <AdminCard
        icon="checkmark-done-outline"
        title="Approve Readings"
        description="Review pending reading submissions"
        onPress={() =>
          navigate("/(tabs)/admin/approve")
        }
      />

      <AdminCard
        icon="book-outline"
        title="Manage Readings"
        description="Edit, publish or remove readings"
        onPress={() =>
          navigate("/(tabs)/admin/reading-management")
        }
      />
      <AdminCard
        icon="document-attach-outline"
        title="Import Readings"
        description="Bulk import liturgical readings from JSON"
        onPress={() =>
          navigate("/(tabs)/admin/readings-import")
        }
      />

      {/* SAINTS & CALENDAR */}
      <Text style={styles.sectionTitle}>
        Saints & Liturgical Calendar
      </Text>

      <AdminCard
        icon="person-circle-outline"
        title="Manage Saints"
        description="Manage saints and feast-day information"
        onPress={() =>
          navigate("/(tabs)/admin/saints")
        }
      />

      <AdminCard
        icon="calendar-outline"
        title="Liturgical Calendar"
        description="Manage seasons, feasts and celebrations"
        onPress={() => navigate("/calendar")}
      />

      {/* CHOIR */}
      <Text style={styles.sectionTitle}>
        Choir Resources
      </Text>

      <AdminCard
        icon="musical-notes-outline"
        title="Manage Choir"
        description="Manage Catholic songs, hymns and resources"
        onPress={() =>
          navigate("/(tabs)/admin/resources")
        }
      />
      <AdminCard
        icon="cloud-upload-outline"
        title="Submit Choir Resource"
        description="Upload audio, video, PDF, or sheet music for review"
        onPress={() => navigate("/(tabs)/admin/upload")}
      />

      {/* CATHOLIC DIRECTORY */}
      <Text style={styles.sectionTitle}>
        Catholic Directory
      </Text>
      <AdminCard
        icon="map-outline"
        title="Manage Directory"
        description="Manage Jurisdictions, Deaneries and Parishes"
        onPress={() => navigate("/(tabs)/admin/manage-directory")}
      />
      <AdminCard
        icon="people-outline"
        title="Parish Requests"
        description="Review pending parish submissions"
        onPress={() => navigate("/(tabs)/admin/parish-requests")}
      />

      {/* USERS */}
      <Text style={styles.sectionTitle}>
        Users & Parish
      </Text>

      <AdminCard
        icon="people-outline"
        title="Manage Users"
        description="View users, roles and account status"
        onPress={() => navigate("/(tabs)/admin/users")}
      />

      <Text style={styles.sectionTitle}>Community Administration</Text>
      <AdminCard
        icon="ribbon-outline"
        title="Review Role Requests"
        description="Review community-role requests within your authorized scope"
        onPress={() => navigate("/role-requests?mode=review")}
      />
      <AdminCard
        icon="people-outline"
        title="Administrators"
        description="View active scoped administrator assignments"
        onPress={() => navigate("/community-admin?section=administrators")}
      />
      <AdminCard
        icon="people-outline"
        title="Verify Parish Memberships"
        description="Approve membership requests for your authorized parish scope"
        onPress={() => navigate("/community-admin?section=memberships")}
      />
      <AdminCard
        icon="megaphone-outline"
        title="Community Announcements"
        description="Create and publish official scoped announcements"
        onPress={() => navigate("/community")}
      />
      <AdminCard
        icon="chatbox-ellipses-outline"
        title="Review Suggestions"
        description="Review private member suggestions within your scope"
        onPress={() => navigate("/community-admin?section=suggestions")}
      />
      <AdminCard
        icon="shield-checkmark-outline"
        title="Audit Log"
        description="View administrative actions available to your scope"
        onPress={() => navigate("/community-audit")}
      />

      {/* BACK */}
      <TouchableOpacity
        style={styles.backButton}
        onPress={() => router.replace("/(tabs)")}
      >
        <Ionicons
          name="arrow-back"
          size={20}
          color="#0B6623"
        />

        <Text style={styles.backText}>
          Back to App
        </Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

function ScopedDashboard({ roles }: { roles: string[] }) {
  const canManageCommunity = roles.some((role) =>
    ["parish_admin", "diocesan_admin"].includes(role),
  );
  const canReview = roles.some((role) =>
    ["parish_admin", "diocesan_admin", "moderator"].includes(role),
  );
  const canManageChoir = roles.some((role) =>
    ["parish_admin", "diocesan_admin", "parish_music_director", "choir_director"].includes(role),
  );

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Community Administration</Text>
          <Text style={styles.subtitle}>Manage only the scopes assigned to your approved role</Text>
        </View>
        <MaterialCommunityIcons name="shield-account" size={28} color="#0B6623" />
      </View>
      {canReview && (
        <AdminCard
          icon="ribbon-outline"
          title="Review Role Requests"
          description="Review requests within your authorized scope"
          onPress={() => router.push("/role-requests?mode=review")}
        />
      )}
      {canManageCommunity && (
        <>
          <AdminCard
            icon="people-outline"
            title="Verify Parish Memberships"
            description="Review membership requests in your assigned scope"
            onPress={() => router.push("/community-admin?section=memberships")}
          />
          <AdminCard
            icon="megaphone-outline"
            title="Community Announcements"
            description="Create scoped announcements"
            onPress={() => router.push("/community")}
          />
          <AdminCard
            icon="shield-checkmark-outline"
            title="Audit Log"
            description="Review administrative actions available to your scope"
            onPress={() => router.push("/community-audit")}
          />
        </>
      )}
      {canManageChoir && (
        <>
          <AdminCard
            icon="cloud-upload-outline"
            title="Submit Choir Resource"
            description="Upload a parish resource for authorized review"
            onPress={() => router.push("/(tabs)/admin/upload")}
          />
          <AdminCard
            icon="musical-notes-outline"
            title="Manage Choir Resources"
            description="Review and manage resources for your parish"
            onPress={() => router.push("/choir")}
          />
        </>
      )}
      <TouchableOpacity style={styles.backButton} onPress={() => router.replace("/(tabs)")}>
        <Ionicons name="arrow-back" size={20} color="#0B6623" />
        <Text style={styles.backText}>Back to App</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

function AdminCard({
  icon,
  title,
  description,
  onPress,
}: {
  icon: ComponentProps<typeof Ionicons>["name"];
  title: string;
  description: string;
  onPress: () => void;
}) {
  return (
    <TouchableOpacity
      style={styles.card}
      onPress={onPress}
      activeOpacity={0.75}
    >
      <View style={styles.iconContainer}>
        <Ionicons
          name={icon}
          size={24}
          color="#0B6623"
        />
      </View>

      <View style={styles.cardContent}>
        <Text style={styles.cardTitle}>
          {title}
        </Text>

        <Text style={styles.cardDescription}>
          {description}
        </Text>
      </View>

      <Ionicons
        name="chevron-forward"
        size={20}
        color="#999"
      />
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  accessState: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 28,
    gap: 12,
    backgroundColor: "#F7F9F7",
  },
  accessTitle: {
    color: "#17351f",
    fontSize: 21,
    fontWeight: "800",
    textAlign: "center",
  },
  accessMessage: {
    color: "#5f6c62",
    textAlign: "center",
    lineHeight: 21,
  },
  retryButton: {
    backgroundColor: "#0B6623",
    paddingVertical: 12,
    paddingHorizontal: 18,
    borderRadius: 9,
    marginTop: 4,
  },
  retryText: { color: "#fff", fontWeight: "700" },
  container: {
    flex: 1,
    backgroundColor: "#F7F9F7",
  },

  content: {
    padding: 18,
    paddingBottom: 40,
  },

  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 28,
  },

  title: {
    fontSize: 28,
    fontWeight: "800",
    color: "#0B6623",
  },

  subtitle: {
    color: "#777",
    fontSize: 13,
    marginTop: 4,
    maxWidth: 280,
  },

  headerIcon: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: "#EAF4ED",
    justifyContent: "center",
    alignItems: "center",
  },

  sectionTitle: {
    fontSize: 19,
    fontWeight: "800",
    color: "#222",
    marginBottom: 11,
    marginTop: 5,
  },

  card: {
    backgroundColor: "#fff",
    borderRadius: 14,
    padding: 14,
    marginBottom: 10,
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#E5EAE6",
  },

  iconContainer: {
    width: 46,
    height: 46,
    borderRadius: 12,
    backgroundColor: "#EAF4ED",
    justifyContent: "center",
    alignItems: "center",
  },

  cardContent: {
    flex: 1,
    marginLeft: 12,
    marginRight: 8,
  },

  cardTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#222",
  },

  cardDescription: {
    color: "#888",
    fontSize: 12,
    lineHeight: 17,
    marginTop: 3,
  },

  backButton: {
    marginTop: 20,
    backgroundColor: "#EAF4ED",
    borderRadius: 12,
    padding: 15,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
  },

  backText: {
    color: "#0B6623",
    fontSize: 16,
    fontWeight: "800",
    marginLeft: 8,
  },
});