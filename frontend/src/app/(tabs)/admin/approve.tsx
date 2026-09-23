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
import AsyncStorage from "@react-native-async-storage/async-storage";
import { Ionicons, MaterialCommunityIcons } from "@expo/vector-icons";
import { api } from "@/lib/api";

interface PendingReading {
  kind: "reading";
  id: number;
  reading_date?: string;
  feast?: string;
  saint_of_day?: string;
  liturgical_year?: string;
  liturgical_season?: string;
  first_reading_reference?: string;
  gospel_reference?: string;
  approved?: boolean;
  published?: boolean;
}

interface PendingResource {
  kind: "resource";
  id: number;
  title: string;
  category?: string;
  description?: string;
  file_type?: string;
}

type PendingItem = PendingReading | PendingResource;

export default function ApproveScreen() {
  const [pending, setPending] = useState<PendingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [processingId, setProcessingId] = useState<number | null>(null);

  useEffect(() => {
    load();
  }, []);

  async function getToken() {
    return AsyncStorage.getItem("access_token");
  }

  async function load(showLoader = true) {
    try {
      if (showLoader) {
        setLoading(true);
      }

      const token = await getToken();

      if (!token) {
        throw new Error("Not authenticated");
      }

      const [readingResponse, resourceResponse] = await Promise.all([
        api.get("/api/admin/pending"),
        api.get("/api/admin/pending-resources"),
      ]);

      const readings = (Array.isArray(readingResponse.data) ? readingResponse.data : [])
        .map((item: Omit<PendingReading, "kind">) => ({ ...item, kind: "reading" as const }));
      const resources = (Array.isArray(resourceResponse.data) ? resourceResponse.data : [])
        .map((item: Omit<PendingResource, "kind">) => ({ ...item, kind: "resource" as const }));

      setPending([...readings, ...resources]);
    } catch (error: any) {
      console.log(
        "Pending readings error:",
        error?.response?.data || error
      );

      setPending([]);

      if (error?.response?.status === 401) {
        Alert.alert(
          "Session Expired",
          "Please log in again."
        );
      } else if (error?.response?.status === 403) {
        Alert.alert(
          "Access Denied",
          "Administrator privileges are required."
        );
      } else if (showLoader) {
        Alert.alert(
          "Error",
          "Unable to load pending readings."
        );
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  async function approve(item: PendingItem) {
    try {
      setProcessingId(item.id);

      const token = await getToken();

      if (!token) {
        Alert.alert(
          "Authentication Required",
          "Please log in again."
        );
        return;
      }

      await api.put(
        item.kind === "reading"
          ? `/api/admin/approve/${item.id}`
          : `/api/admin/approve-resource/${item.id}`,
        {},
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
          timeout: 15000,
        }
      );

      setPending((current) =>
        current.filter((currentItem) => currentItem !== item)
      );

      Alert.alert(
        "Approved",
        "The reading has been approved and published."
      );
    } catch (error: any) {
      console.log(
        "Approve error:",
        error?.response?.data || error
      );

      Alert.alert(
        "Approval Failed",
        error?.response?.data?.detail ||
          "Unable to approve this reading."
      );
    } finally {
      setProcessingId(null);
    }
  }

  async function reject(item: PendingItem) {
    Alert.alert(
      "Reject Reading",
      "Are you sure you want to delete this pending reading?",
      [
        {
          text: "Cancel",
          style: "cancel",
        },
        {
          text: "Reject",
          style: "destructive",
          onPress: async () => {
            try {
              setProcessingId(item.id);

              const token = await getToken();

              if (!token) {
                Alert.alert(
                  "Authentication Required",
                  "Please log in again."
                );
                return;
              }

              await api.delete(
                item.kind === "reading"
                  ? `/api/admin/readings/${item.id}`
                  : `/api/admin/resources/${item.id}`,
                {
                  headers: {
                    Authorization: `Bearer ${token}`,
                  },
                  timeout: 15000,
                }
              );

              setPending((current) =>
                  current.filter((currentItem) => currentItem !== item)
              );

              Alert.alert(
                "Rejected",
                "The reading has been removed."
              );
            } catch (error: any) {
              Alert.alert(
                "Rejection Failed",
                error?.response?.data?.detail ||
                  "Unable to reject this reading."
              );
            } finally {
              setProcessingId(null);
            }
          },
        },
      ]
    );
  }

  function renderItem({
    item,
  }: {
    item: PendingItem;
  }) {
    const processing =
      processingId === item.id;

    return (
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <View style={styles.icon}>
            <MaterialCommunityIcons
              name="book-open-page-variant"
              size={25}
              color="#0B6623"
            />
          </View>

          <View style={styles.heading}>
            <Text style={styles.feast}>
              {item.kind === "resource"
                ? item.title
                : item.feast || item.saint_of_day || "Pending Reading"}
            </Text>

            {item.kind === "reading" && item.reading_date ? (
              <Text style={styles.date}>
                {item.reading_date}
              </Text>
            ) : null}
          </View>
        </View>

        <View style={styles.metaRow}>
          {item.kind === "resource" && item.category ? (
            <Text style={styles.tag}>{item.category}</Text>
          ) : null}

          {item.kind === "reading" && item.liturgical_year ? (
            <Text style={styles.tag}>
              Year {item.liturgical_year}
            </Text>
          ) : null}

          {item.kind === "reading" && item.liturgical_season ? (
            <Text style={styles.tag}>
              {item.liturgical_season}
            </Text>
          ) : null}
        </View>

        {item.kind === "reading" && item.first_reading_reference ? (
          <Text style={styles.reference}>
            First Reading:{" "}
            {item.first_reading_reference}
          </Text>
        ) : null}

        {item.kind === "reading" && item.gospel_reference ? (
          <Text style={styles.reference}>
            Gospel: {item.gospel_reference}
          </Text>
        ) : null}

        <View style={styles.actions}>
          <TouchableOpacity
            style={[
              styles.approveButton,
              processing &&
                styles.disabledButton,
            ]}
            disabled={processing}
            onPress={() => approve(item)}
          >
            {processing ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <>
                <Ionicons
                  name="checkmark-circle-outline"
                  size={19}
                  color="#fff"
                />

                <Text style={styles.buttonText}>
                  Approve
                </Text>
              </>
            )}
          </TouchableOpacity>

          <TouchableOpacity
            style={[
              styles.rejectButton,
              processing &&
                styles.disabledButton,
            ]}
            disabled={processing}
            onPress={() => reject(item)}
          >
            <Ionicons
              name="close-circle-outline"
              size={19}
              color="#fff"
            />

            <Text style={styles.buttonText}>
              Reject
            </Text>
          </TouchableOpacity>
        </View>
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
          Loading pending readings...
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>
            Pending Readings
          </Text>

          <Text style={styles.subtitle}>
            Review and approve submitted readings
          </Text>
        </View>

        <TouchableOpacity
          style={styles.refreshButton}
          onPress={() => load(false)}
        >
          <Ionicons
            name="refresh"
            size={21}
            color="#0B6623"
          />
        </TouchableOpacity>
      </View>

      <FlatList
        data={pending}
        keyExtractor={(item) =>
          item.id.toString()
        }
        renderItem={renderItem}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={async () => {
              setRefreshing(true);
              await load(false);
            }}
            colors={["#0B6623"]}
          />
        }
        contentContainerStyle={
          pending.length === 0
            ? styles.emptyContainer
            : styles.list
        }
        ListEmptyComponent={
          <View style={styles.empty}>
            <MaterialCommunityIcons
              name="check-all"
              size={55}
              color="#0B6623"
            />

            <Text style={styles.emptyTitle}>
              All caught up
            </Text>

            <Text style={styles.emptyText}>
              There are no readings waiting for
              approval.
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
    backgroundColor: "#fff",
    justifyContent: "center",
    alignItems: "center",
  },

  loadingText: {
    marginTop: 10,
    color: "#666",
  },

  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 18,
  },

  title: {
    fontSize: 27,
    fontWeight: "800",
    color: "#0B6623",
  },

  subtitle: {
    color: "#777",
    fontSize: 13,
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

  list: {
    paddingBottom: 30,
  },

  card: {
    backgroundColor: "#fff",
    borderRadius: 15,
    padding: 16,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: "#E5EAE6",
  },

  cardHeader: {
    flexDirection: "row",
    alignItems: "center",
  },

  icon: {
    width: 47,
    height: 47,
    borderRadius: 24,
    backgroundColor: "#EAF4ED",
    justifyContent: "center",
    alignItems: "center",
    marginRight: 11,
  },

  heading: {
    flex: 1,
  },

  feast: {
    fontSize: 17,
    fontWeight: "800",
    color: "#222",
  },

  date: {
    color: "#777",
    fontSize: 13,
    marginTop: 3,
  },

  metaRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    marginTop: 12,
  },

  tag: {
    backgroundColor: "#EAF4ED",
    color: "#0B6623",
    paddingHorizontal: 9,
    paddingVertical: 5,
    borderRadius: 14,
    marginRight: 7,
    marginBottom: 5,
    fontSize: 11,
    fontWeight: "700",
  },

  reference: {
    color: "#666",
    marginTop: 7,
    fontSize: 13,
  },

  actions: {
    flexDirection: "row",
    marginTop: 16,
  },

  approveButton: {
    flex: 1,
    backgroundColor: "#0B6623",
    minHeight: 46,
    borderRadius: 10,
    justifyContent: "center",
    alignItems: "center",
    flexDirection: "row",
    marginRight: 7,
  },

  rejectButton: {
    flex: 1,
    backgroundColor: "#C62828",
    minHeight: 46,
    borderRadius: 10,
    justifyContent: "center",
    alignItems: "center",
    flexDirection: "row",
    marginLeft: 7,
  },

  disabledButton: {
    opacity: 0.6,
  },

  buttonText: {
    color: "#fff",
    fontWeight: "800",
    marginLeft: 6,
  },

  emptyContainer: {
    flexGrow: 1,
  },

  empty: {
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 30,
    marginTop: 90,
  },

  emptyTitle: {
    fontSize: 19,
    fontWeight: "800",
    color: "#444",
    marginTop: 15,
  },

  emptyText: {
    color: "#888",
    textAlign: "center",
    marginTop: 7,
    lineHeight: 20,
  },
});