import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { Ionicons, MaterialCommunityIcons } from "@expo/vector-icons";
import { api } from "@/lib/api";

interface Reading {
  id: number;
  feast?: string;
  saint_of_day?: string;
  first_reading_reference: string;
  first_reading: string;
  responsorial_psalm_reference?: string;
  responsorial_psalm?: string;
  second_reading_reference?: string;
  second_reading?: string;
  gospel_reference: string;
  gospel: string;
}

const categories = [
  "All",
  "First Reading",
  "Psalm",
  "Second Reading",
  "Gospel",
];

export default function Readings() {
  const [readings, setReadings] = useState<Reading[]>([]);
  const [filtered, setFiltered] = useState<Reading[]>([]);
  const [selectedCategory, setSelectedCategory] =
    useState("All");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadReadings();
  }, []);

  useEffect(() => {
    if (selectedCategory === "All") {
      setFiltered(readings);
    } else {
      setFiltered(
        readings.filter(
          (reading) => {
            const category = selectedCategory.toLowerCase();
            return category === "first reading"
              ? Boolean(reading.first_reading)
              : category === "psalm"
              ? Boolean(reading.responsorial_psalm)
              : category === "second reading"
              ? Boolean(reading.second_reading)
              : category === "gospel"
              ? Boolean(reading.gospel)
              : false;
          }
        )
      );
    }
  }, [readings, selectedCategory]);

  async function loadReadings() {
    try {
      setLoading(true);

      const response = await api.get("/api/readings/today");
      setReadings([response.data]);
    } catch (error) {
      console.log(
        "Readings error:",
        error
      );

      setReadings([]);

      Alert.alert(
        "Error",
        "Unable to load today's readings."
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  async function refresh() {
    setRefreshing(true);
    await loadReadings();
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

  function renderReading({
    item,
  }: {
    item: Reading;
  }) {
    const entries = [
      ["First Reading", item.first_reading_reference, item.first_reading],
      ["Psalm", item.responsorial_psalm_reference, item.responsorial_psalm],
      ["Second Reading", item.second_reading_reference, item.second_reading],
      ["Gospel", item.gospel_reference, item.gospel],
    ].filter((entry): entry is [string, string, string] => Boolean(entry[2]));

    return (
      <View style={styles.card}>
        {entries.map(([type, reference, content]) => (
          <View key={type} style={styles.readingSection}>
            <View style={styles.cardHeader}>
              <View style={styles.iconContainer}>
                <MaterialCommunityIcons
                  name={getIcon(type)}
                  size={25}
                  color="#0B6623"
                />
              </View>
              <View style={styles.headerText}>
                <Text style={styles.type}>{type}</Text>
                <Text style={styles.reference}>{reference}</Text>
              </View>
            </View>
            <Text style={styles.content}>{content}</Text>
          </View>
        ))}
      </View>
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
          Loading readings...
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* HEADER */}
      <View style={styles.header}>
        <View>
          <Text style={styles.heading}>
            Daily Readings
          </Text>

          <Text style={styles.subtitle}>
            Catholic Scripture for today
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

      {/* TODAY */}
      <View style={styles.today}>
        <MaterialCommunityIcons
          name="calendar-today"
          size={23}
          color="#fff"
        />

        <View style={styles.todayText}>
          <Text style={styles.todayTitle}>
            Today's Readings
          </Text>

          <Text style={styles.todayDate}>
            {new Date().toLocaleDateString(
              undefined,
              {
                weekday: "long",
                day: "numeric",
                month: "long",
                year: "numeric",
              }
            )}
          </Text>
        </View>
      </View>

      {/* CATEGORIES */}
      <FlatList
        horizontal
        data={categories}
        keyExtractor={(item) => item}
        showsHorizontalScrollIndicator={false}
        style={styles.categories}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={[
              styles.category,
              selectedCategory === item &&
                styles.categoryActive,
            ]}
            onPress={() =>
              setSelectedCategory(item)
            }
          >
            <Text
              style={[
                styles.categoryText,
                selectedCategory === item &&
                  styles.categoryTextActive,
              ]}
            >
              {item}
            </Text>
          </TouchableOpacity>
        )}
      />

      {/* READINGS */}
      <FlatList
        data={filtered}
        keyExtractor={(item, index) =>
          item.id
            ? item.id.toString()
            : index.toString()
        }
        renderItem={renderReading}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={refresh}
            colors={["#0B6623"]}
          />
        }
        contentContainerStyle={
          filtered.length === 0
            ? styles.emptyContainer
            : styles.list
        }
        ListEmptyComponent={
          <View style={styles.empty}>
            <MaterialCommunityIcons
              name="book-off-outline"
              size={55}
              color="#aaa"
            />

            <Text style={styles.emptyTitle}>
              No readings available
            </Text>

            <Text style={styles.emptyText}>
              Pull down to refresh the readings.
            </Text>
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
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: "#EAF4ED",
    justifyContent: "center",
    alignItems: "center",
  },

  today: {
    backgroundColor: "#0B6623",
    borderRadius: 15,
    padding: 16,
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 15,
  },

  todayText: {
    marginLeft: 12,
  },

  todayTitle: {
    color: "#fff",
    fontSize: 17,
    fontWeight: "800",
  },

  todayDate: {
    color: "#DDEFE2",
    fontSize: 13,
    marginTop: 3,
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
    marginBottom: 12,
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

  title: {
    fontSize: 19,
    fontWeight: "800",
    color: "#222",
    marginBottom: 10,
  },

  content: {
    fontSize: 16,
    color: "#444",
    lineHeight: 25,
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
    readingSection: {
      marginBottom: 14,
    },
});