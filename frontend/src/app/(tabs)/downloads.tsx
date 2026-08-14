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

  // Optional expanded resource information
  category?: string;
  description?: string;
  language?: string;
  season?: string;
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

      const token =
        await AsyncStorage.getItem("access_token");

      const response = await axios.get(
        `${API_URL}/api/downloads`,
        {
          headers: token
            ? {
                Authorization: `Bearer ${token}`,
              }
            : {},
        }
      );

      const data = Array.isArray(response.data)
        ? response.data
        : response.data?.items || [];

      setDownloads(data);
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
    if (!url) {
      Alert.alert(
        "Unavailable",
        "This resource has no file URL."
      );
      return;
    }

    try {
      const supported =
        await Linking.canOpenURL(url);

      if (!supported) {
        Alert.alert(
          "Cannot Open",
          "This file cannot be opened on this device."
        );
        return;
      }

      await Linking.openURL(url);
    } catch {
      Alert.alert(
        "Error",
        "Unable to open this resource."
      );
    }
  }

  function getIcon(fileType: string) {
    const type =
      fileType?.toLowerCase() || "";

    if (type.includes("audio")) return "🎵";
    if (type.includes("video")) return "🎬";
    if (type.includes("pdf")) return "📄";
    if (type.includes("image")) return "🖼️";
    if (type.includes("sheet")) return "🎼";
    if (type.includes("lyrics")) return "📝";

    return "📁";
  }

  function formatDate(date: string) {
    if (!date) return "Unknown date";

    const parsed = new Date(date);

    if (Number.isNaN(parsed.getTime())) {
      return date;
    }

    return parsed.toLocaleDateString(
      undefined,
      {
        day: "numeric",
        month: "short",
        year: "numeric",
      }
    );
  }

  function renderItem({
    item,
  }: {
    item: DownloadItem;
  }) {
    return (
      <View style={styles.card}>
        <View style={styles.topRow}>
          <Text style={styles.icon}>
            {getIcon(item.file_type)}
          </Text>

          <View style={styles.titleContainer}>
            <Text style={styles.title}>
              {item.title}
            </Text>

            {item.category ? (
              <Text style={styles.category}>
                {item.category}
              </Text>
            ) : null}
          </View>
        </View>

        {item.description ? (
          <Text
            style={styles.description}
            numberOfLines={3}
          >
            {item.description}
          </Text>
        ) : null}

        <View style={styles.tags}>
          <Text style={styles.tag}>
            {item.file_type?.toUpperCase() ||
              "FILE"}
          </Text>

          {item.language ? (
            <Text style={styles.tag}>
              {item.language}
            </Text>
          ) : null}

          {item.season ? (
            <Text style={styles.tag}>
              {item.season}
            </Text>
          ) : null}
        </View>

        <Text style={styles.date}>
          Downloaded:{" "}
          {formatDate(item.downloaded_at)}
        </Text>

        <TouchableOpacity
          style={styles.button}
          onPress={() =>
            openResource(item.file_url)
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

        <Text style={styles.loadingText}>
          Loading downloads...
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.header}>
        Offline Downloads
      </Text>

      <Text style={styles.subtitle}>
        Your saved Catholic readings and
        choir resources
      </Text>

      <View style={styles.countBox}>
        <Text style={styles.countNumber}>
          {downloads.length}
        </Text>

        <Text style={styles.countLabel}>
          Saved Resources
        </Text>
      </View>

      <FlatList
        data={downloads}
        keyExtractor={(item) =>
          item.id.toString()
        }
        renderItem={renderItem}
        contentContainerStyle={
          downloads.length === 0
            ? styles.emptyContainer
            : styles.list
        }
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={refresh}
            colors={["#0B6623"]}
          />
        }
        ListEmptyComponent={
          <View style={styles.emptyBox}>
            <Text style={styles.emptyIcon}>
              📥
            </Text>

            <Text style={styles.empty}>
              No downloaded resources
            </Text>

            <Text style={styles.emptyHint}>
              Resources that you download will
              appear here for easy access.
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
    backgroundColor: "#fff",
    paddingHorizontal: 15,
    paddingTop: 18,
  },

  loading: {
    flex: 1,
    backgroundColor: "#fff",
    justifyContent: "center",
    alignItems: "center",
  },

  loadingText: {
    marginTop: 10,
    color: "#666",
  },

  header: {
    fontSize: 28,
    fontWeight: "bold",
    color: "#0B6623",
  },

  subtitle: {
    color: "#666",
    marginTop: 5,
    marginBottom: 18,
  },

  countBox: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#eaf4ed",
    borderRadius: 12,
    padding: 14,
    marginBottom: 18,
  },

  countNumber: {
    fontSize: 25,
    fontWeight: "bold",
    color: "#0B6623",
    marginRight: 10,
  },

  countLabel: {
    color: "#555",
    fontWeight: "600",
  },

  list: {
    paddingBottom: 30,
  },

  card: {
    backgroundColor: "#fafafa",
    borderRadius: 14,
    padding: 16,
    marginBottom: 15,
    borderWidth: 1,
    borderColor: "#eee",
    elevation: 2,
  },

  topRow: {
    flexDirection: "row",
    alignItems: "center",
  },

  icon: {
    fontSize: 30,
    marginRight: 12,
  },

  titleContainer: {
    flex: 1,
  },

  title: {
    fontSize: 18,
    fontWeight: "700",
    color: "#222",
  },

  category: {
    color: "#0B6623",
    fontWeight: "600",
    marginTop: 4,
  },

  description: {
    color: "#666",
    lineHeight: 20,
    marginTop: 12,
  },

  tags: {
    flexDirection: "row",
    flexWrap: "wrap",
    marginTop: 10,
  },

  tag: {
    backgroundColor: "#e9f3ec",
    color: "#0B6623",
    fontSize: 11,
    fontWeight: "700",
    paddingHorizontal: 9,
    paddingVertical: 5,
    borderRadius: 15,
    marginRight: 6,
    marginBottom: 5,
  },

  date: {
    color: "#777",
    marginTop: 8,
    marginBottom: 14,
    fontSize: 13,
  },

  button: {
    backgroundColor: "#0B6623",
    padding: 13,
    borderRadius: 10,
    alignItems: "center",
  },

  buttonText: {
    color: "#fff",
    fontWeight: "700",
    fontSize: 15,
  },

  emptyContainer: {
    flexGrow: 1,
  },

  emptyBox: {
    alignItems: "center",
    paddingHorizontal: 30,
    marginTop: 70,
  },

  emptyIcon: {
    fontSize: 50,
    marginBottom: 15,
  },

  empty: {
    textAlign: "center",
    color: "#777",
    fontSize: 17,
    fontWeight: "600",
  },

  emptyHint: {
    textAlign: "center",
    color: "#aaa",
    marginTop: 8,
    lineHeight: 20,
  },
});