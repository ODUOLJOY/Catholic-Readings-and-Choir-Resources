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
  Linking,
} from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import axios from "axios";

const API_URL =
  "https://catholic-readings-and-choir-resource-app.onrender.com";

interface ChoirResource {
  id: number;
  title: string;
  category: string;
  description: string;
  file_type: string;
  file_url: string;
  created_at: string;
}

const categories = [
  "All",
  "Entrance",
  "Offertory",
  "Communion",
  "Recessional",
  "Marian",
  "Christmas",
  "Easter",
  "Lent",
  "Advent",
  "Wedding",
  "Funeral",
];

export default function Choir() {
  const [resources, setResources] = useState<ChoirResource[]>([]);
  const [filtered, setFiltered] = useState<ChoirResource[]>([]);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadResources();
  }, []);

  useEffect(() => {
    filterResources();
  }, [search, category, resources]);

  async function loadResources() {
    try {
      setLoading(true);

      const token = await AsyncStorage.getItem("access_token");

      const response = await axios.get(
        `${API_URL}/api/choir`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      setResources(response.data);
    } catch (err) {
      Alert.alert(
        "Error",
        "Unable to load choir resources."
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  function filterResources() {
    let data = [...resources];

    if (category !== "All") {
      data = data.filter(
        item => item.category === category
      );
    }

    if (search.trim()) {
      data = data.filter(item =>
        item.title
          .toLowerCase()
          .includes(search.toLowerCase())
      );
    }

    setFiltered(data);
  }

  async function refresh() {
    setRefreshing(true);
    await loadResources();
  }

  async function openFile(url: string) {
    const supported = await Linking.canOpenURL(url);

    if (!supported) {
      Alert.alert("Cannot open file.");
      return;
    }

    Linking.openURL(url);
  }

  function renderItem({
    item,
  }: {
    item: ChoirResource;
  }) {
    return (
      <View style={styles.card}>
        <Text style={styles.songTitle}>
          {item.title}
        </Text>

        <Text style={styles.category}>
          {item.category}
        </Text>

        <Text style={styles.description}>
          {item.description}
        </Text>

        <Text style={styles.type}>
          {item.file_type.toUpperCase()}
        </Text>

        <TouchableOpacity
          style={styles.button}
          onPress={() =>
            openFile(item.file_url)
          }
        >
          <Text style={styles.buttonText}>
            Open Resource
          </Text>
        </TouchableOpacity>
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
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>
        Choir Resources
      </Text>

      <TextInput
        placeholder="Search choir songs..."
        style={styles.search}
        value={search}
        onChangeText={setSearch}
      />

      <FlatList
        horizontal
        showsHorizontalScrollIndicator={false}
        data={categories}
        keyExtractor={(item) => item}
        style={{ marginBottom: 15 }}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={[
              styles.categoryButton,
              category === item &&
                styles.categoryActive,
            ]}
            onPress={() =>
              setCategory(item)
            }
          >
            <Text
              style={[
                styles.categoryText,
                category === item && {
                  color: "#fff",
                },
              ]}
            >
              {item}
            </Text>
          </TouchableOpacity>
        )}
      />

      <FlatList
        data={filtered}
        keyExtractor={(item) =>
          item.id.toString()
        }
        renderItem={renderItem}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={refresh}
          />
        }
        ListEmptyComponent={
          <Text style={styles.empty}>
            No choir resources found.
          </Text>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#fff",
    padding: 15,
  },

  loading: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },

  title: {
    fontSize: 28,
    fontWeight: "bold",
    color: "#0B6623",
    marginBottom: 15,
  },

  search: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 10,
    padding: 12,
    marginBottom: 15,
  },

  categoryButton: {
    paddingHorizontal: 15,
    paddingVertical: 8,
    borderRadius: 25,
    borderWidth: 1,
    borderColor: "#0B6623",
    marginRight: 10,
    height: 40,
  },

  categoryActive: {
    backgroundColor: "#0B6623",
  },

  categoryText: {
    color: "#0B6623",
    fontWeight: "600",
  },

  card: {
    backgroundColor: "#fafafa",
    padding: 15,
    borderRadius: 12,
    marginBottom: 15,
    elevation: 2,
  },

  songTitle: {
    fontSize: 19,
    fontWeight: "700",
  },

  category: {
    color: "#0B6623",
    marginTop: 4,
    fontWeight: "600",
  },

  description: {
    marginVertical: 10,
    color: "#555",
  },

  type: {
    color: "#777",
    marginBottom: 10,
  },

  button: {
    backgroundColor: "#0B6623",
    padding: 12,
    borderRadius: 10,
  },

  buttonText: {
    color: "#fff",
    textAlign: "center",
    fontWeight: "700",
  },

  empty: {
    marginTop: 60,
    textAlign: "center",
    color: "#888",
    fontSize: 16,
  },
});