import {
  Alert,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { router } from "expo-router";
import {
  Ionicons,
  MaterialCommunityIcons,
} from "@expo/vector-icons";

export default function Dashboard() {
  function navigate(path: string) {
    router.push(path as any);
  }

  function comingSoon(feature: string) {
    Alert.alert(
      "Coming Soon",
      `${feature} management will be available here.`
    );
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
        title="Upload Reading"
        description="Add daily readings and liturgical content"
        onPress={() =>
          navigate("/(tabs)/admin/upload")
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
          navigate("/(tabs)/admin/readings")
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
        onPress={() =>
          comingSoon("Liturgical Calendar")
        }
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
          navigate("/choir")
        }
      />

      <AdminCard
        icon="cloud-upload-outline"
        title="Upload Choir Resource"
        description="Add audio, lyrics, PDF and video resources"
        onPress={() =>
          navigate("/(tabs)/admin/upload")
        }
      />

      <AdminCard
        icon="folder-open-outline"
        title="Choir Categories"
        description="Entrance, Kyrie, Gloria, Psalms, Offertory, Communion and more"
        onPress={() =>
          comingSoon("Choir Categories")
        }
      />

      {/* USERS */}
      <Text style={styles.sectionTitle}>
        Users & Parish
      </Text>

      <AdminCard
        icon="people-outline"
        title="Manage Users"
        description="View users, roles and account status"
        onPress={() =>
          comingSoon("User Management")
        }
      />

      <AdminCard
        icon="business-outline"
        title="Manage Parishes"
        description="Manage parish accounts and assignments"
        onPress={() =>
          comingSoon("Parish Management")
        }
      />

      {/* REPORTS */}
      <Text style={styles.sectionTitle}>
        Reports & System
      </Text>

      <AdminCard
        icon="flag-outline"
        title="Reports"
        description="Review reported content and resources"
        onPress={() =>
          comingSoon("Reports")
        }
      />

      <AdminCard
        icon="bar-chart-outline"
        title="Analytics"
        description="View usage and content statistics"
        onPress={() =>
          comingSoon("Analytics")
        }
      />

      <AdminCard
        icon="settings-outline"
        title="Admin Settings"
        description="Configure administration settings"
        onPress={() =>
          comingSoon("Admin Settings")
        }
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

function AdminCard({
  icon,
  title,
  description,
  onPress,
}: {
  icon: any;
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

const styles = StyleSheet.create<any>({
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