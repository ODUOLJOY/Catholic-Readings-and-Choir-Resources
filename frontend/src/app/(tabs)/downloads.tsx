import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Linking,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import axios from "axios";

const API_URL =
  "https://catholic-readings-and-choir-resource-app.onrender.com";

interface DownloadItem {
  id: number;
  title: string;
  file_type: string;
  file_url: string;
  downloaded_at: string;
}

export default function Downloads() {
  const [downloads, setDownloads] = useState<DownloadItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadDownloads();
  }, []);

  async function loadDownloads() {
    try {
      setLoading(true);

      const token = await AsyncStorage.getItem("access_token");

      const response = await axios.get(
        `${API_URL}/api/downloads`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      setDownloads(response.data);
    } catch (error) {
      Alert.alert(
        "Error",
        "Unable to load downloaded resources."
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  async function refresh() {
    setRefreshing(true);
    await loadDownloads();
  }

  async function openResource(url: string) {
    const supported = await Linking.canOpenURL(url);

    if (!supported) {
      Alert.alert("Cannot open file.");
      return;
    }

    await Linking.openURL(url);
  }

  function renderItem({
    item,
  }: {
    item: DownloadItem;
  }) {
    return (
      <View style={styles.card}>
        <Text style={styles.title}>
          {item.title}
        </Text>

        <Text style={styles.type}>
          {item.file_type.toUpperCase()}
        </Text>

        <Text style={styles.date}>
          Downloaded:
          {" "}
          {new Date(
            item.downloaded_at
          ).toLocaleDateString()}
        </Text>

        <TouchableOpacity
          style={styles.button}
          onPress={() =>
            openResource(item.file_url)
          }
        >
          <Text style={styles.buttonText}>
            Open
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
      <Text style={styles.header}>
        Offline Downloads
      </Text>

      <FlatList
        data={downloads}
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
            No downloaded resources found.
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

  header: {
    fontSize: 28,
    fontWeight: "bold",
    color: "#0B6623",
    marginBottom: 20,
  },

  card: {
    backgroundColor: "#fafafa",
    borderRadius: 12,
    padding: 15,
    marginBottom: 15,
    elevation: 2,
  },

  title: {
    fontSize: 18,
    fontWeight: "700",
    marginBottom: 5,
  },

  type: {
    color: "#0B6623",
    fontWeight: "600",
    marginBottom: 5,
  },

  date: {
    color: "#666",
    marginBottom: 15,
  },

  button: {
    backgroundColor: "#0B6623",
    padding: 12,
    borderRadius: 10,
    alignItems: "center",
  },

  buttonText: {
    color: "#fff",
    fontWeight: "700",
    fontSize: 16,
  },

  empty: {
    textAlign: "center",
    marginTop: 60,
    color: "#888",
    fontSize: 16,
  },
});