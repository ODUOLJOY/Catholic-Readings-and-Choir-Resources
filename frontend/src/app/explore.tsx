import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import {
  Ionicons,
  MaterialCommunityIcons,
} from "@expo/vector-icons";
import axios from "axios";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { router } from "expo-router";

const API_URL =
  "https://catholic-readings-and-choir-resource-app.onrender.com";

interface SearchResult {
  id?: number | string;
  title: string;
  type?: string;
  description?: string;
  category?: string;
  file_url?: string;
  reference?: string;
}

const quickActions = [
  {
    title: "Daily Readings",
    description: "Today's Catholic Scripture",
    icon: "book-open-page-variant",
    route: "/readings",
  },
  {
    title: "Liturgical Calendar",
    description: "Feasts, seasons and celebrations",
    icon: "calendar-month",
    route: "/calendar",
  },
  {
    title: "Choir Resources",
    description: "Catholic songs and hymns",
    icon: "music-note-multiple",
    route: "/choir",
  },
  {
    title: "Favorites",
    description: "Your saved resources",
    icon: "star",
    route: "/favorites",
  },
  {
    title: "Downloads",
    description: "Offline resources",
    icon: "download",
    route: "/downloads",
  },
  {
    title: "Profile",
    description: "Account and settings",
    icon: "account-circle",
    route: "/profile",
  },
];

export default function ExploreScreen() {
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searched, setSearched] = useState(false);

  useEffect(() => {
    searchEverything("");
  }, []);

  async function searchEverything(query = search) {
    try {
      setLoading(true);
      setSearched(true);

      const token =
        await AsyncStorage.getItem("access_token");

      const response = await axios.get(
        `${API_URL}/api/search`,
        {
          params: {
            q: query.trim(),
          },
          headers: token
            ? {
                Authorization: `Bearer ${token}`,
              }
            : {},
          timeout: 15000,
        }
      );

      const data = Array.isArray(response.data)
        ? response.data
        : response.data?.results ||
          response.data?.items ||
          [];

      setResults(data);
    } catch (error: any) {
      console.log(
        "Search error:",
        error?.response?.data || error
      );

      setResults([]);

      Alert.alert(
        "Search Error",
        "Unable to search Catholic resources."
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  async function refresh() {
    setRefreshing(true);
    await searchEverything(search);
  }

  function openAction(route: string) {
    router.push(route as any);
  }

  function renderAction({
    item,
  }: {
    item: (typeof quickActions)[number];
  }) {
    return (
      <TouchableOpacity
        style={styles.actionCard}
        onPress={() => openAction(item.route)}
        activeOpacity={0.75}
      >
        <View style={styles.actionIcon}>
          <MaterialCommunityIcons
            name={item.icon as any}
            size={25}
            color="#0B6623"
          />
        </View>

        <View style={styles.actionText}>
          <Text style={styles.actionTitle}>
            {item.title}
          </Text>

          <Text style={styles.actionDescription}>
            {item.description}
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

  function renderResult({
    item,
  }: {
    item: SearchResult;
  }) {
    return (
      <TouchableOpacity
        style={styles.result}
        activeOpacity={0.8}
      >
        <View style={styles.resultIcon}>
          <MaterialCommunityIcons
            name="book-open-outline"
            size={23}
            color="#0B6623"
          />
        </View>

        <View style={styles.resultContent}>
          <Text style={styles.resultTitle}>
            {item.title || "Untitled Resource"}
          </Text>

          {(item.type || item.category) && (
            <Text style={styles.resultType}>
              {item.type || item.category}
            </Text>
          )}

          {item.reference && (
            <Text style={styles.reference}>
              {item.reference}
            </Text>
          )}

          {item.description && (
            <Text
              style={styles.resultDescription}
              numberOfLines={3}
            >
              {item.description}
            </Text>
          )}
        </View>
      </TouchableOpacity>
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={results}
        keyExtractor={(item, index) =>
          String(item.id ?? index)
        }
        renderItem={renderResult}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={refresh}
            colors={["#0B6623"]}
          />
        }
        contentContainerStyle={styles.content}
        ListHeaderComponent={
          <>
            {/* HEADER */}
            <View style={styles.header}>
              <View>
                <Text style={styles.title}>
                  Explore
                </Text>

                <Text style={styles.subtitle}>
                  Discover Catholic resources
                </Text>
              </View>

              <View style={styles.headerIcon}>
                <MaterialCommunityIcons
                  name="church"
                  size={28}
                  color="#0B6623"
                />
              </View>
            </View>

            {/* SEARCH */}
            <View style={styles.searchContainer}>
              <Ionicons
                name="search"
                size={21}
                color="#777"
              />

              <TextInput
                placeholder="Search readings, saints, hymns..."
                placeholderTextColor="#999"
                style={styles.input}
                value={search}
                onChangeText={setSearch}
                onSubmitEditing={() =>
                  searchEverything(search)
                }
                returnKeyType="search"
              />

              {search.length > 0 && (
                <TouchableOpacity
                  onPress={() => {
                    setSearch("");
                    searchEverything("");
                  }}
                >
                  <Ionicons
                    name="close-circle"
                    size={21}
                    color="#999"
                  />
                </TouchableOpacity>
              )}
            </View>

            <TouchableOpacity
              style={styles.searchButton}
              onPress={() =>
                searchEverything(search)
              }
            >
              <Ionicons
                name="search"
                size={19}
                color="#fff"
              />

              <Text style={styles.searchText}>
                Search
              </Text>
            </TouchableOpacity>

            {/* QUICK ACCESS */}
            <Text style={styles.sectionTitle}>
              Quick Access
            </Text>

            <View style={styles.actions}>
              {quickActions.map((item) =>
                renderAction({ item })
              )}
            </View>

            {/* SEARCH RESULTS HEADER */}
            {searched && (
              <View style={styles.resultsHeader}>
                <Text style={styles.sectionTitle}>
                  Search Results
                </Text>

                {!loading && (
                  <Text style={styles.resultCount}>
                    {results.length} found
                  </Text>
                )}
              </View>
            )}

            {loading && (
              <View style={styles.loading}>
                <ActivityIndicator
                  size="large"
                  color="#0B6623"
                />

                <Text style={styles.loadingText}>
                  Searching...
                </Text>
              </View>
            )}
          </>
        }
        ListEmptyComponent={
          !loading ? (
            <View style={styles.empty}>
              <View style={styles.emptyIcon}>
                <MaterialCommunityIcons
                  name="magnify-close"
                  size={45}
                  color="#0B6623"
                />
              </View>

              <Text style={styles.emptyTitle}>
                No results found
              </Text>

              <Text style={styles.emptyText}>
                Try searching for a reading, saint,
                feast, hymn, choir song or Catholic
                resource.
              </Text>
            </View>
          ) : null
        }
      />
    </View>
  );
}

const styles = StyleSheet.create<any>({
  container: {
    flex: 1,
    backgroundColor: "#F7F9F7",
  },

  content: {
    padding: 18,
    paddingBottom: 35,
  },

  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 20,
  },

  title: {
    fontSize: 30,
    fontWeight: "800",
    color: "#0B6623",
  },

  subtitle: {
    color: "#777",
    marginTop: 3,
    fontSize: 14,
  },

  headerIcon: {
    width: 50,
    height: 50,
    borderRadius: 25,
    backgroundColor: "#EAF4ED",
    justifyContent: "center",
    alignItems: "center",
  },

  searchContainer: {
    height: 54,
    backgroundColor: "#fff",
    borderRadius: 14,
    borderWidth: 1,
    borderColor: "#E0E5E1",
    paddingHorizontal: 15,
    flexDirection: "row",
    alignItems: "center",
  },

  input: {
    flex: 1,
    fontSize: 15,
    color: "#222",
    marginLeft: 10,
  },

  searchButton: {
    height: 50,
    backgroundColor: "#0B6623",
    borderRadius: 13,
    marginTop: 10,
    marginBottom: 25,
    justifyContent: "center",
    alignItems: "center",
    flexDirection: "row",
  },

  searchText: {
    color: "#fff",
    fontWeight: "800",
    fontSize: 16,
    marginLeft: 8,
  },

  sectionTitle: {
    fontSize: 19,
    fontWeight: "800",
    color: "#222",
    marginBottom: 12,
  },

  actions: {
    marginBottom: 20,
  },

  actionCard: {
    backgroundColor: "#fff",
    borderRadius: 14,
    padding: 13,
    marginBottom: 9,
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#E5EAE6",
  },

  actionIcon: {
    width: 46,
    height: 46,
    borderRadius: 12,
    backgroundColor: "#EAF4ED",
    justifyContent: "center",
    alignItems: "center",
  },

  actionText: {
    flex: 1,
    marginLeft: 12,
  },

  actionTitle: {
    fontSize: 16,
    fontWeight: "750",
    color: "#222",
  },

  actionDescription: {
    color: "#888",
    fontSize: 12,
    marginTop: 3,
  },

  resultsHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 5,
  },

  resultCount: {
    color: "#777",
    fontSize: 13,
    marginBottom: 12,
  },

  loading: {
    alignItems: "center",
    paddingVertical: 25,
  },

  loadingText: {
    color: "#777",
    marginTop: 8,
  },

  result: {
    backgroundColor: "#fff",
    borderRadius: 14,
    padding: 14,
    marginBottom: 12,
    flexDirection: "row",
    borderWidth: 1,
    borderColor: "#E5EAE6",
  },

  resultIcon: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: "#EAF4ED",
    justifyContent: "center",
    alignItems: "center",
  },

  resultContent: {
    flex: 1,
    marginLeft: 12,
  },

  resultTitle: {
    fontSize: 17,
    fontWeight: "750",
    color: "#222",
  },

  resultType: {
    color: "#0B6623",
    fontWeight: "700",
    fontSize: 12,
    marginTop: 4,
  },

  reference: {
    color: "#777",
    fontSize: 12,
    marginTop: 3,
  },

  resultDescription: {
    color: "#555",
    fontSize: 13,
    lineHeight: 19,
    marginTop: 7,
  },

  empty: {
    alignItems: "center",
    paddingHorizontal: 30,
    paddingVertical: 35,
  },

  emptyIcon: {
    width: 75,
    height: 75,
    borderRadius: 38,
    backgroundColor: "#EAF4ED",
    justifyContent: "center",
    alignItems: "center",
    marginBottom: 15,
  },

  emptyTitle: {
    fontSize: 19,
    fontWeight: "800",
    color: "#444",
  },

  emptyText: {
    textAlign: "center",
    color: "#888",
    lineHeight: 20,
    marginTop: 7,
  },
});