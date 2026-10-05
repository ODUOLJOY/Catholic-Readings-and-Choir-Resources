import { useCallback, useEffect, useState } from "react";
import { router } from "expo-router";
import {
  RefreshControl,
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
import { authService } from "@/services/authService";
import { isAdminRole } from "@/lib/roles";
import { CHOIR_CATEGORIES } from "@/config/choirCategories";

type TodayLiturgy = {
  date: string;
  celebration: { name: string; rank: string };
  liturgical: { colour: string; season: string };
  readings: { type: string; display_reference: string }[];
};

export default function Home() {
  const [liturgy, setLiturgy] = useState<TodayLiturgy | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);

  const loadLiturgy = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const response = await api.get("/api/v1/liturgy/today");
      setLiturgy(response.data);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(loadLiturgy);
  }, [loadLiturgy]);

  // The Admin shortcut is hidden until a stored role says the member may use it.
  // The same check gates the Admin tab; the server enforces it regardless.
  useEffect(() => {
    let active = true;
    void authService
      .getRole()
      .then((role) => {
        if (active) {
          setIsAdmin(isAdminRole(role));
        }
      })
      .catch(() => {
        if (active) {
          setIsAdmin(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  async function onRefresh() {
    setRefreshing(true);
    await loadLiturgy();
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => void onRefresh()}
          tintColor="#0B6623"
          colors={["#0B6623"]}
        />
      }
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
      ) : error ? (
        <View style={styles.heroError}>
          <Text style={styles.errorText}>Unable to load today&apos;s liturgy.</Text>
          <Pressable onPress={() => void loadLiturgy()}>
            <Text style={styles.retryText}>Retry</Text>
          </Pressable>
        </View>
      ) : liturgy ? (
        <View style={styles.hero}>
          <Text style={styles.heroTitle}>{liturgy.celebration.name}</Text>
          <Text style={styles.heroText}>
            {liturgy.date} | {liturgy.liturgical.colour} | {liturgy.liturgical.season}
          </Text>
          {liturgy.readings.length > 0 && (
            <View style={styles.readingsSection}>
              <Text style={styles.sectionTitle}>Readings</Text>
              {liturgy.readings.map((reading, index) => (
                <Text key={`${reading.type}-${index}`} style={styles.readingItem}>
                  {reading.type.replaceAll("_", " ")}: {reading.display_reference}
                </Text>
              ))}
            </View>
          )}
        </View>
      ) : null}

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

      {/* EXPLORE */}
      <Pressable
        style={styles.mainCard}
        onPress={() => router.push("/explore")}
      >
        <View style={styles.iconCircle}>
          <Ionicons name="search-outline" size={28} color="#0B6623" />
        </View>
        <View style={styles.cardContent}>
          <Text style={styles.cardTitle}>
            Explore &amp; Search
          </Text>

          <Text style={styles.cardText}>
            Search readings, saints and choir resources together.
          </Text>
        </View>

        <Ionicons
          name="chevron-forward"
          size={24}
          color="#777"
        />
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
            {liturgy?.celebration.name || "Today's readings"}
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
            Manage choir resources you have downloaded.
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
        {/* Canonical 27 categories, in the specified order. This grid previously
            carried its own 16-item hand-written list: eleven canonical
            categories were unreachable from Home (Sadaka, Agnus Dei,
            Benediction, Holy Week, Ordinary Time, Rosary, Baptism, Saints,
            Latin, Choir Practice, Others) and the order did not match the rest
            of the app. */}
        {CHOIR_CATEGORIES.map((category) => (
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
      {isAdmin ? (
        <Pressable
          style={styles.adminButton}
          onPress={() => router.push("/admin")}
          accessibilityRole="button"
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
      ) : null}
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

  heroError: {
    backgroundColor: "#FFF4F2",
    borderColor: "#E9B6AE",
    borderWidth: 1,
    borderRadius: 12,
    padding: 16,
    marginBottom: 20,
  },

  errorText: {
    color: "#7D2720",
    fontSize: 15,
    marginBottom: 8,
  },

  retryText: {
    color: "#0B6623",
    fontWeight: "700",
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