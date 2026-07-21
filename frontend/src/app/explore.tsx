import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
  Alert,
} from "react-native";
import axios from "axios";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { router } from "expo-router";

const API_URL =
  "https://catholic-readings-and-choir-resource-app.onrender.com";

export default function ExploreScreen() {
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const [results, setResults] = useState<any[]>([]);

  useEffect(() => {
    searchEverything();
  }, []);

  async function searchEverything(query = "") {
    try {
      setLoading(true);

      const token = await AsyncStorage.getItem("access_token");

      const response = await axios.get(
        `${API_URL}/api/search`,
        {
          params: {
            q: query,
          },
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      setResults(response.data);
    } catch (error) {
      Alert.alert(
        "Search Error",
        "Unable to search resources."
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

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={refresh}
        />
      }
    >
      <Text style={styles.title}>
        Explore Catholic Resources
      </Text>

      <TextInput
        placeholder="Search readings, saints, feasts, choir songs..."
        style={styles.input}
        value={search}
        onChangeText={setSearch}
        onSubmitEditing={() =>
          searchEverything(search)
        }
      />

      <TouchableOpacity
        style={styles.searchButton}
        onPress={() =>
          searchEverything(search)
        }
      >
        <Text style={styles.searchText}>
          Search
        </Text>
      </TouchableOpacity>

      <View style={styles.quickActions}>
        <TouchableOpacity
          style={styles.card}
          onPress={() =>
            router.push("/readings")
          }
        >
          <Text style={styles.cardTitle}>
            📖 Daily Readings
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.card}
          onPress={() =>
            router.push("/calendar")
          }
        >
          <Text style={styles.cardTitle}>
            📅 Liturgical Calendar
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.card}
          onPress={() =>
            router.push("/choir")
          }
        >
          <Text style={styles.cardTitle}>
            🎵 Choir Resources
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.card}
          onPress={() =>
            router.push("/favorites")
          }
        >
          <Text style={styles.cardTitle}>
            ⭐ Favorites
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.card}
          onPress={() =>
            router.push("/downloads")
          }
        >
          <Text style={styles.cardTitle}>
            ⬇ Downloads
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.card}
          onPress={() =>
            router.push("/profile")
          }
        >
          <Text style={styles.cardTitle}>
            👤 Profile
          </Text>
        </TouchableOpacity>
      </View>

      {loading ? (
        <ActivityIndicator
          size="large"
          color="#0B6623"
          style={{ marginTop: 30 }}
        />
      ) : (
        results.map((item, index) => (
          <View
            key={index}
            style={styles.result}
          >
            <Text style={styles.resultTitle}>
              {item.title}
            </Text>

            <Text style={styles.resultType}>
              {item.type}
            </Text>

            <Text>
              {item.description}
            </Text>
          </View>
        ))
      )}

      {!loading &&
        results.length === 0 && (
          <Text style={styles.empty}>
            No results found.
          </Text>
        )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#fff",
    padding: 18,
  },

  title: {
    fontSize: 28,
    fontWeight: "bold",
    color: "#0B6623",
    marginBottom: 20,
  },

  input: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 12,
    padding: 14,
    marginBottom: 12,
  },

  searchButton: {
    backgroundColor: "#0B6623",
    padding: 15,
    borderRadius: 12,
    marginBottom: 20,
  },

  searchText: {
    color: "#fff",
    textAlign: "center",
    fontWeight: "700",
    fontSize: 16,
  },

  quickActions: {
    marginBottom: 25,
  },

  card: {
    backgroundColor: "#F5F5F5",
    padding: 18,
    borderRadius: 12,
    marginBottom: 12,
  },

  cardTitle: {
    fontSize: 17,
    fontWeight: "700",
    color: "#0B6623",
  },

  result: {
    backgroundColor: "#fafafa",
    borderRadius: 12,
    padding: 16,
    marginBottom: 15,
    elevation: 2,
  },

  resultTitle: {
    fontSize: 18,
    fontWeight: "700",
    marginBottom: 5,
  },

  resultType: {
    color: "#0B6623",
    fontWeight: "600",
    marginBottom: 8,
  },

  empty: {
    textAlign: "center",
    marginTop: 40,
    color: "#777",
    fontSize: 16,
  },
});