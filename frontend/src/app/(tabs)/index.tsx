import { useState, useEffect } from "react";
import { router } from "expo-router";
import {
  ScrollView,
  View,
  Text,
  Pressable,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import {
  Ionicons,
  MaterialCommunityIcons,
} from "@expo/vector-icons";
import { api } from "@/lib/api";

export default function Home() {
  const [liturgy, setLiturgy] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/api/v1/liturgy/today")
      .then((res) => {
        setLiturgy(res.data);
      })
      .catch((err) => {
        console.error("Failed to load liturgy:", err);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      {/* HEADER */}
      <View style={styles.header}>
        <View style={styles.logo}>
          <MaterialCommunityIcons
            name="church"
            size={34}
            color="#fff"
          />
        </View>

        <View>
          <Text style={styles.welcome}>
            Welcome
          </Text>

          <Text style={styles.appName}>
            Catholic Readings
          </Text>
        </View>
      </View>

      {/* TODAY'S CELEBRATION */}
      {loading ? (
        <ActivityIndicator size="large" color="#0B6623" />
      ) : liturgy && (
        <View style={styles.hero}>
          <Text style={styles.heroTitle}>{liturgy.calendar.celebration}</Text>
          <Text style={styles.heroText}>
            {liturgy.calendar.date} | {liturgy.calendar.color} | {liturgy.calendar.season}
          </Text>
          {liturgy.calendar.selected_reading_set && (
            <View style={styles.readingsSection}>
              <Text style={styles.sectionTitle}>Readings</Text>
              <Text style={styles.readingItem}>1st: {liturgy.calendar.selected_reading_set.first_reading}</Text>
              <Text style={styles.readingItem}>Psalm: {liturgy.calendar.selected_reading_set.psalm}</Text>
              {liturgy.calendar.selected_reading_set.second_reading && (
                <Text style={styles.readingItem}>2nd: {liturgy.calendar.selected_reading_set.second_reading}</Text>
              )}
              <Text style={styles.readingItem}>Gospel: {liturgy.calendar.selected_reading_set.gospel}</Text>
            </View>
          )}
        </View>
      )}

      <Pressable
        style={styles.mainCard}
        onPress={() => router.push("/community")}
      >
        <View style={styles.iconCircle}>
          <Ionicons name="people-outline" size={28} color="#0B6623" />
        </View>
        <View style={styles.cardContent}>
          <Text style={styles.cardTitle}>Parish Community</Text>
          <Text style={styles.cardText}>
            Official announcements, events, prayer intentions, suggestions and member conversation.
          </Text>
        </View>
        <Ionicons name="chevron-forward" size={24} color="#777" />
      </Pressable>

      {/* DAILY READINGS */}
      <Pressable
        style={styles.mainCard}
        onPress={() => router.push("/readings")}
      >
        <View style={styles.iconCircle}>
          <MaterialCommunityIcons
            name="book-open-page-variant"
            size={28}
            color="#0B6623"
          />
        </View>

        <View style={styles.cardContent}>
          <Text style={styles.cardTitle}>
            Daily Readings
          </Text>

          <Text style={styles.cardText}>
            {liturgy?.reading?.feast || "Today's readings"}
          </Text>
        </View>

        <Ionicons
          name="chevron-forward"
          size={24}
          color="#777"
        />
      </Pressable>

      {/* CHOIR */}
      <Pressable
        style={styles.mainCard}
        onPress={() => router.push("/choir")}
      >
        <View style={styles.iconCircle}>
          <MaterialCommunityIcons
            name="music-box-multiple"
            size={28}
            color="#0B6623"
          />
        </View>

        <View style={styles.cardContent}>
          <Text style={styles.cardTitle}>
            Choir Resources
          </Text>

          <Text style={styles.cardText}>
            Entrance, Kyrie, Gloria, Psalms,
            Offertory, Communion, Thanksgiving,
            Exit and seasonal songs.
          </Text>
        </View>

        <Ionicons
          name="chevron-forward"
          size={24}
          color="#777"
        />
      </Pressable>

      {/* DOWNLOADS */}
      <Pressable
        style={styles.mainCard}
        onPress={() => router.push("/downloads")}
      >
        <View style={styles.iconCircle}>
          <Ionicons
            name="download-outline"
            size={28}
            color="#0B6623"
          />
        </View>

        <View style={styles.cardContent}>
          <Text style={styles.cardTitle}>
            Offline Downloads
          </Text>

          <Text style={styles.cardText}>
            Access your saved readings and choir
            resources even when offline.
          </Text>
        </View>

        <Ionicons
          name="chevron-forward"
          size={24}
          color="#777"
        />
      </Pressable>

      {/* SUBSCRIPTION */}
      <Pressable
        style={styles.subscriptionCard}
        onPress={() => router.push("/(tabs)/payment")}
      >
        <View style={styles.subscriptionIcon}>
          <MaterialCommunityIcons
            name="cellphone-check"
            size={28}
            color="#fff"
          />
        </View>

        <View style={styles.cardContent}>
          <Text style={styles.subscriptionTitle}>
            Monthly Subscription
          </Text>

          <Text style={styles.subscriptionText}>
            Support the app with KES 10 via M-Pesa.
          </Text>
        </View>

        <Ionicons
          name="chevron-forward"
          size={24}
          color="#fff"
        />
      </Pressable>

      {/* CATEGORIES */}
      <Text style={styles.sectionTitle}>
        Choir Categories
      </Text>

      <View style={styles.categoryGrid}>
        {[
          "Entrance",
          "Kyrie & Gloria",
          "Psalms",
          "Gospel Acclamation",
          "Offertory",
          "Communion",
          "Thanksgiving",
          "Exit",
          "Lent",
          "Advent",
          "Christmas",
          "Easter",
          "Pentecost",
          "Marian",
          "Wedding",
          "Funeral",
        ].map((category) => (
          <Pressable
            key={category}
            style={styles.category}
            onPress={() =>
              router.push({
                pathname: "/choir",
                params: { category },
              })
            }
          >
            <MaterialCommunityIcons
              name="music-note"
              size={18}
              color="#0B6623"
            />

            <Text style={styles.categoryText}>
              {category}
            </Text>
          </Pressable>
        ))}
      </View>

      {/* ADMIN */}
      <Pressable
        style={styles.adminButton}
        onPress={() => router.push("/admin")}
      >
        <MaterialCommunityIcons
          name="shield-account"
          size={22}
          color="#fff"
        />

        <Text style={styles.adminText}>
          Admin Panel
        </Text>
      </Pressable>
    </ScrollView>
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

  header: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 20,
  },

  logo: {
    width: 55,
    height: 55,
    borderRadius: 16,
    backgroundColor: "#0B6623",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },

  welcome: {
    color: "#777",
    fontSize: 14,
  },

  appName: {
    color: "#0B6623",
    fontSize: 21,
    fontWeight: "800",
  },

  hero: {
    backgroundColor: "#0B6623",
    borderRadius: 20,
    padding: 24,
    marginBottom: 20,
  },

  heroTitle: {
    color: "#fff",
    fontSize: 27,
    fontWeight: "800",
    lineHeight: 34,
  },

  heroText: {
    color: "#E8F4EB",
    fontSize: 15,
    lineHeight: 22,
    marginTop: 12,
  },

  mainCard: {
    backgroundColor: "#fff",
    borderRadius: 16,
    padding: 16,
    marginBottom: 13,
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#E6EAE7",
  },

  subscriptionCard: {
    backgroundColor: "#0B6623",
    borderRadius: 16,
    padding: 16,
    marginBottom: 13,
    flexDirection: "row",
    alignItems: "center",
  },

  subscriptionIcon: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: "#2C8445",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 13,
  },

  subscriptionTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: "#fff",
    marginBottom: 4,
  },

  subscriptionText: {
    fontSize: 13,
    lineHeight: 19,
    color: "#E8F4EB",
  },

  iconCircle: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: "#EAF4ED",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 13,
  },

  cardContent: {
    flex: 1,
    marginRight: 8,
  },

  cardTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: "#222",
    marginBottom: 4,
  },

  cardText: {
    fontSize: 13,
    lineHeight: 19,
    color: "#777",
  },

  sectionTitle: {
    fontSize: 21,
    fontWeight: "800",
    color: "#222",
    marginTop: 15,
    marginBottom: 12,
  },
  readingsSection: {
    marginTop: 10,
    backgroundColor: "#F9FAF9",
    padding: 10,
    borderRadius: 8,
  },
  readingItem: {
    fontSize: 14,
    color: "#444",
    marginBottom: 4,
  },

  categoryGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
  },

  category: {
    width: "48%",
    minHeight: 52,
    backgroundColor: "#fff",
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginBottom: 10,
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#E6EAE7",
  },

  categoryText: {
    flex: 1,
    marginLeft: 8,
    color: "#333",
    fontSize: 13,
    fontWeight: "600",
  },

  adminButton: {
    marginTop: 12,
    backgroundColor: "#333",
    borderRadius: 12,
    padding: 15,
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    gap: 8,
  },

  adminText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "700",
  },
});