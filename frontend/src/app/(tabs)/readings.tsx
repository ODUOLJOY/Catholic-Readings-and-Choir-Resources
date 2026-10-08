import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons, MaterialCommunityIcons } from "@expo/vector-icons";
import { api } from "@/lib/api";
import { requestErrorMessage } from "@/lib/requestFailure";
import { LiturgicalCache } from "@/services/liturgicalCache";
import { formatKenyaDate, kenyaDateString, shiftCalendarDate } from "@/utils/calendar";

interface ReadingReference {
  type: string;
  book: string;
  display_reference: string;
  is_alternative: boolean;
  is_optional: boolean;
  is_primary: boolean;
}

interface LiturgicalDay {
  date: string;
  region: string;
  celebration: {
    name: string;
    rank: string;
  };
  liturgical: {
    season: string;
    week: number | null;
    colour: string;
    sunday_cycle: string;
    weekday_cycle: string;
  };
  readings: ReadingReference[];
  available_reading_sets: any[];
  source: {
    name: string | null;
    region: string;
  } | null;
  verification_status: string;
}

const categories: string[] = [
  "All",
  "First Reading",
  "Psalm",
  "Second Reading",
  "Gospel",
];

export default function Readings() {
  const { date: dateParam } = useLocalSearchParams<{ date: string }>();
  const router = useRouter();
  const [currentDate, setCurrentDate] = useState<string>(dateParam || kenyaDateString());
  const [liturgicalDay, setLiturgicalDay] = useState<LiturgicalDay | null>(null);
  const [selectedCategory, setSelectedCategory] = useState("All");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showCalendar, setShowCalendar] = useState(false);
  const [isFromCache, setIsFromCache] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  
  const filtered = useMemo(() => {
    if (!liturgicalDay || selectedCategory === "All") {
      return liturgicalDay?.readings || [];
    }

    return liturgicalDay.readings.filter((reading) => {
      const type = reading.type.toLowerCase();
      switch (selectedCategory.toLowerCase()) {
        case "first reading":
          return type === "first_reading";
        case "psalm":
          return type === "responsorial_psalm";
        case "second reading":
          return type === "second_reading";
        case "gospel":
          return type === "gospel";
        default:
          return false;
      }
    });
  }, [liturgicalDay, selectedCategory]);

  async function loadReadings(dateStr: string) {
    try {
      setLoading(true);
      setIsFromCache(false);
      setApiError(null);

      // Try to load from cache first
      const cached = await LiturgicalCache.get(dateStr, "KE");
      if (cached) {
        setLiturgicalDay(cached);
        setIsFromCache(true);
        setLoading(false);
        return;
      }

      // Fetch from API
      const endpoint = `/api/v1/liturgy/date/${dateStr}`;
      const response = await api.get(endpoint);
      setLiturgicalDay(response.data);
      
      // Cache the response
      await LiturgicalCache.set(dateStr, "KE", response.data);
    } catch (error) {
      setApiError(
        requestErrorMessage(
          error,
          "Unable to load readings. Check your connection and try again.",
        ),
      );
      setLiturgicalDay(null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    void Promise.resolve().then(() => loadReadings(currentDate));
  }, [currentDate]);

  async function refresh() {
    setRefreshing(true);
    await loadReadings(currentDate);
  }

  function navigateDate(direction: number) {
    const newDateStr = shiftCalendarDate(currentDate, direction);
    setCurrentDate(newDateStr);
    router.setParams({ date: newDateStr });
  }

  function goToToday() {
    const today = kenyaDateString();
    setCurrentDate(today);
    router.setParams({ date: today });
  }

  function getIcon(type: string) {
    const value = type.toLowerCase();

    if (value.includes("gospel")) {
      return "book-open-page-variant";
    }

    if (value.includes("psalm")) {
      return "music-note";
    }

    return "book-open";
  }

  function getReadingTypeLabel(type: string): string {
    const typeMap: Record<string, string> = {
      FIRST_READING: "First Reading",
      RESPONSORIAL_PSALM: "Responsorial Psalm",
      SECOND_READING: "Second Reading",
      GOSPEL_ACCLAMATION: "Gospel Acclamation",
      GOSPEL: "Gospel",
    };
    return typeMap[type] || type;
  }

  function renderReading({ item }: { item: ReadingReference }) {
    return (
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <View style={styles.iconContainer}>
            <MaterialCommunityIcons
              name={getIcon(item.type)}
              size={25}
              color="#0B6623"
            />
          </View>
          <View style={styles.headerText}>
            <Text style={styles.type}>{getReadingTypeLabel(item.type)}</Text>
            <Text style={styles.reference}>{item.display_reference}</Text>
            {item.book && <Text style={styles.book}>{item.book}</Text>}
            {item.is_alternative && <Text style={styles.badge}>Alternative</Text>}
            {item.is_optional && <Text style={styles.badge}>Optional</Text>}
          </View>
        </View>
      </View>
    );
  }

  if (loading) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator size="large" color="#0B6623" />
        <Text style={styles.loadingText}>Loading readings...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* HEADER */}
      <View style={styles.header}>
        <View>
          <Text style={styles.heading}>Daily Readings</Text>
          <Text style={styles.subtitle}>Catholic Scripture for today</Text>
        </View>
        <View style={styles.headerActions}>
          {isFromCache && (
            <TouchableOpacity style={styles.cacheButton}>
              <MaterialCommunityIcons name="cloud-check" size={20} color="#F59E0B" />
            </TouchableOpacity>
          )}
          <TouchableOpacity style={styles.refreshButton} onPress={refresh}>
            <Ionicons name="refresh" size={22} color="#0B6623" />
          </TouchableOpacity>
        </View>
      </View>

      {/* ERROR BANNER */}
      {apiError ? (
        <View style={styles.errorBanner}>
          <Ionicons name="alert-circle" size={16} color="#b91c1c" />
          <Text style={styles.errorBannerText}>{apiError}</Text>
        </View>
      ) : null}

      {/* DATE NAVIGATION */}
      <View style={styles.dateNavigation}>
        <TouchableOpacity style={styles.navButton} onPress={() => navigateDate(-1)}>
          <Ionicons name="chevron-back" size={24} color="#0B6623" />
        </TouchableOpacity>
        
        <TouchableOpacity style={styles.dateButton} onPress={goToToday}>
          <MaterialCommunityIcons name="calendar-today" size={20} color="#0B6623" />
          <Text style={styles.dateText}>
            {formatKenyaDate(currentDate)}
          </Text>
        </TouchableOpacity>
        
        <TouchableOpacity style={styles.navButton} onPress={() => navigateDate(1)}>
          <Ionicons name="chevron-forward" size={24} color="#0B6623" />
        </TouchableOpacity>
      </View>

      {/* LITURGICAL INFO */}
      {liturgicalDay && (
        <View style={styles.liturgicalInfo}>
          <View style={styles.liturgicalRow}>
            <MaterialCommunityIcons name="church" size={20} color="#0B6623" />
            <Text style={styles.liturgicalLabel}>{liturgicalDay.celebration.name}</Text>
            <Text style={styles.liturgicalBadge}>{liturgicalDay.celebration.rank}</Text>
          </View>
          <View style={styles.liturgicalRow}>
            <MaterialCommunityIcons name="palette" size={20} color={liturgicalDay.liturgical.colour === "Red" ? "#C41E3A" : liturgicalDay.liturgical.colour === "White" ? "#F5F5F5" : liturgicalDay.liturgical.colour === "Purple" ? "#8E44AD" : "#0B6623"} />
            <Text style={styles.liturgicalLabel}>{liturgicalDay.liturgical.season}</Text>
            {liturgicalDay.liturgical.week && <Text style={styles.liturgicalValue}>Week {liturgicalDay.liturgical.week}</Text>}
            <Text style={styles.liturgicalValue}>({liturgicalDay.liturgical.colour})</Text>
          </View>
          <View style={styles.liturgicalRow}>
            <MaterialCommunityIcons name="bookmark" size={20} color="#0B6623" />
            <Text style={styles.liturgicalLabel}>Year {liturgicalDay.liturgical.sunday_cycle}</Text>
            <Text style={styles.liturgicalValue}>({liturgicalDay.liturgical.weekday_cycle})</Text>
          </View>
          {liturgicalDay.verification_status !== "verified" && (
            <View style={styles.liturgicalRow}>
              <MaterialCommunityIcons name="alert-circle" size={20} color="#F59E0B" />
              <Text style={styles.liturgicalValue}>Unverified</Text>
            </View>
          )}
        </View>
      )}

      {/* CATEGORIES */}
      <FlatList
        horizontal
        data={categories}
        keyExtractor={(item) => item}
        showsHorizontalScrollIndicator={false}
        style={styles.categories}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={[styles.category, selectedCategory === item && styles.categoryActive]}
            onPress={() => setSelectedCategory(item)}
          >
            <Text style={[styles.categoryText, selectedCategory === item && styles.categoryTextActive]}>
              {item}
            </Text>
          </TouchableOpacity>
        )}
      />

      {/* READINGS */}
      <FlatList
        data={filtered}
        keyExtractor={(item, index) => `${item.type}-${index}`}
        renderItem={renderReading}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={refresh} colors={["#0B6623"]} />
        }
        contentContainerStyle={filtered.length === 0 ? styles.emptyContainer : styles.list}
        ListEmptyComponent={
          <View style={styles.empty}>
            <MaterialCommunityIcons name="book-off-outline" size={55} color="#aaa" />
            <Text style={styles.emptyTitle}>No readings available</Text>
            <Text style={styles.emptyText}>Pull down to refresh the readings.</Text>
          </View>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F7F9F7",
    paddingHorizontal: 15,
    paddingTop: 18,
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
    marginBottom: 15,
  },

  headerActions: {
    flexDirection: "row",
    alignItems: "center",
  },

  cacheButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "#FEF3C7",
    justifyContent: "center",
    alignItems: "center",
    marginRight: 8,
  },

  errorBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "#FEF2F2",
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginBottom: 12,
  },

  errorBannerText: {
    color: "#b91c1c",
    fontSize: 13,
    flex: 1,
  },

  heading: {
    fontSize: 28,
    fontWeight: "800",
    color: "#0B6623",
  },

  subtitle: {
    color: "#777",
    marginTop: 4,
  },

  refreshButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "#EAF4ED",
    justifyContent: "center",
    alignItems: "center",
  },

  dateNavigation: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: "#fff",
    borderRadius: 15,
    padding: 12,
    marginBottom: 15,
    borderWidth: 1,
    borderColor: "#E5EAE6",
  },

  navButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "#EAF4ED",
    justifyContent: "center",
    alignItems: "center",
  },

  dateButton: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    marginHorizontal: 12,
  },

  dateText: {
    fontSize: 16,
    fontWeight: "600",
    color: "#0B6623",
    marginLeft: 8,
  },

  liturgicalInfo: {
    backgroundColor: "#fff",
    borderRadius: 15,
    padding: 16,
    marginBottom: 15,
    borderWidth: 1,
    borderColor: "#E5EAE6",
  },

  liturgicalRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 8,
  },

  liturgicalLabel: {
    marginLeft: 10,
    fontSize: 14,
    color: "#444",
    fontWeight: "500",
    flex: 1,
  },

  liturgicalBadge: {
    fontSize: 11,
    fontWeight: "600",
    color: "#0B6623",
    backgroundColor: "#EAF4ED",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
    marginLeft: 8,
  },

  liturgicalValue: {
    marginLeft: 5,
    fontSize: 13,
    color: "#777",
    fontStyle: "italic",
  },

  categories: {
    marginBottom: 15,
    maxHeight: 45,
  },

  category: {
    paddingHorizontal: 15,
    paddingVertical: 9,
    borderRadius: 22,
    borderWidth: 1,
    borderColor: "#0B6623",
    backgroundColor: "#fff",
    marginRight: 8,
  },

  categoryActive: {
    backgroundColor: "#0B6623",
  },

  categoryText: {
    color: "#0B6623",
    fontWeight: "600",
    fontSize: 13,
  },

  categoryTextActive: {
    color: "#fff",
  },

  list: {
    paddingBottom: 30,
  },

  card: {
    backgroundColor: "#fff",
    borderRadius: 15,
    padding: 17,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: "#E5EAE6",
  },

  cardHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 8,
  },

  iconContainer: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: "#EAF4ED",
    justifyContent: "center",
    alignItems: "center",
    marginRight: 12,
  },

  headerText: {
    flex: 1,
  },

  type: {
    color: "#0B6623",
    fontSize: 14,
    fontWeight: "800",
    textTransform: "uppercase",
  },

  reference: {
    color: "#777",
    marginTop: 3,
    fontSize: 13,
  },

  book: {
    color: "#555",
    marginTop: 2,
    fontSize: 13,
    fontStyle: "italic",
  },

  badge: {
    fontSize: 10,
    fontWeight: "600",
    color: "#666",
    backgroundColor: "#F3F4F6",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
    marginTop: 4,
    alignSelf: "flex-start",
  },

  emptyContainer: {
    flexGrow: 1,
  },

  empty: {
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 30,
    marginTop: 70,
  },

  emptyTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: "#555",
    marginTop: 15,
  },

  emptyText: {
    color: "#999",
    textAlign: "center",
    marginTop: 7,
  },
});