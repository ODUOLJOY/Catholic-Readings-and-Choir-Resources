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
import AsyncStorage from "@react-native-async-storage/async-storage";
import {
  Ionicons,
  MaterialCommunityIcons,
} from "@expo/vector-icons";
import { api } from "@/lib/api";

interface Saint {
  id: number;
  name: string;
  feast_date: string;
  description?: string;
  biography?: string;
  patronage?: string;
  country?: string;
  liturgical_rank?: string;
  image_url?: string;
}

export default function SaintsScreen() {
  const [saints, setSaints] = useState<Saint[]>([]);
  const [filtered, setFiltered] = useState<Saint[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [search, setSearch] = useState("");

  const [showAddForm, setShowAddForm] =
    useState(false);

  const [name, setName] = useState("");
  const [feastDate, setFeastDate] = useState("");
  const [description, setDescription] =
    useState("");
  const [biography, setBiography] =
    useState("");
  const [patronage, setPatronage] =
    useState("");
  const [country, setCountry] =
    useState("");
  const [rank, setRank] = useState(
    "Memorial"
  );

  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadSaints();
  }, []);

  useEffect(() => {
    filterSaints();
  }, [saints, search]);

  async function getToken() {
    return AsyncStorage.getItem(
      "access_token"
    );
  }

  async function loadSaints(
    showLoader = true
  ) {
    try {
      if (showLoader) {
        setLoading(true);
      }

      const token = await getToken();

      const response = await api.get(
        "/api/saints/",
        {
          headers: token
            ? {
                Authorization: `Bearer ${token}`,
              }
            : {},
          timeout: 15000,
        }
      );

      const data = Array.isArray(
        response.data
      )
        ? response.data
        : response.data?.items ||
          response.data?.saints ||
          [];

      setSaints(data);
    } catch (error: any) {
      console.log(
        "Saints error:",
        error?.response?.data || error
      );

      setSaints([]);

      if (showLoader) {
        Alert.alert(
          "Error",
          "Unable to load saints."
        );
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  function filterSaints() {
    const query = search.trim().toLowerCase();

    if (!query) {
      setFiltered(saints);
      return;
    }

    setFiltered(
      saints.filter((saint) => {
        return (
          saint.name
            ?.toLowerCase()
            .includes(query) ||
          saint.feast_date
            ?.toLowerCase()
            .includes(query) ||
          saint.description
            ?.toLowerCase()
            .includes(query) ||
          saint.patronage
            ?.toLowerCase()
            .includes(query) ||
          saint.country
            ?.toLowerCase()
            .includes(query)
        );
      })
    );
  }

  async function refresh() {
    setRefreshing(true);
    await loadSaints(false);
  }

  function clearForm() {
    setName("");
    setFeastDate("");
    setDescription("");
    setBiography("");
    setPatronage("");
    setCountry("");
    setRank("Memorial");
  }

  async function addSaint() {
    if (!name.trim() || !feastDate.trim()) {
      Alert.alert(
        "Missing Information",
        "Saint name and feast date are required."
      );
      return;
    }

    try {
      setSaving(true);

      const token = await getToken();

      if (!token) {
        Alert.alert(
          "Authentication Required",
          "Please log in as an administrator."
        );
        return;
      }

      await api.post(
        "/api/saints/",
        {
          name: name.trim(),
          feast_date: feastDate.trim(),
          description:
            description.trim() || null,
          biography:
            biography.trim() || null,
          patronage:
            patronage.trim() || null,
          country:
            country.trim() || null,
          liturgical_rank: rank,
        },
        {
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          timeout: 15000,
        }
      );

      clearForm();
      setShowAddForm(false);

      await loadSaints(false);

      Alert.alert(
        "Success",
        "Saint added successfully."
      );
    } catch (error: any) {
      console.log(
        "Add saint error:",
        error?.response?.data || error
      );

      Alert.alert(
        "Error",
        error?.response?.data?.detail ||
          "Unable to add saint."
      );
    } finally {
      setSaving(false);
    }
  }

  async function deleteSaint(id: number) {
    Alert.alert(
      "Delete Saint",
      "Are you sure you want to delete this saint?",
      [
        {
          text: "Cancel",
          style: "cancel",
        },
        {
          text: "Delete",
          style: "destructive",
          onPress: async () => {
            try {
              const token = await getToken();

              if (!token) {
                Alert.alert(
                  "Authentication Required",
                  "Please log in again."
                );
                return;
              }

              await api.delete(
                `/api/saints/${id}`,
                {
                  headers: {
                    Authorization: `Bearer ${token}`,
                  },
                  timeout: 15000,
                }
              );

              setSaints((current) =>
                current.filter(
                  (saint) => saint.id !== id
                )
              );

              Alert.alert(
                "Deleted",
                "Saint removed successfully."
              );
            } catch (error: any) {
              Alert.alert(
                "Delete Failed",
                error?.response?.data?.detail ||
                  "Unable to delete saint."
              );
            }
          },
        },
      ]
    );
  }

  function formatDate(value: string) {
    if (!value) return "";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return value;
    }

    return date.toLocaleDateString(
      undefined,
      {
        day: "numeric",
        month: "long",
        year: "numeric",
      }
    );
  }

  function renderSaint({
    item,
  }: {
    item: Saint;
  }) {
    return (
      <View style={styles.card}>
        <View style={styles.cardTop}>
          <View style={styles.iconCircle}>
            <MaterialCommunityIcons
              name="account-star"
              size={25}
              color="#0B6623"
            />
          </View>

          <View style={styles.cardHeading}>
            <Text style={styles.saintName}>
              {item.name}
            </Text>

            <Text style={styles.feastDate}>
              Feast: {formatDate(item.feast_date)}
            </Text>
          </View>
        </View>

        {item.liturgical_rank ? (
          <View style={styles.tag}>
            <Text style={styles.tagText}>
              {item.liturgical_rank}
            </Text>
          </View>
        ) : null}

        {item.description ? (
          <Text
            style={styles.description}
            numberOfLines={3}
          >
            {item.description}
          </Text>
        ) : null}

        {item.biography ? (
          <Text
            style={styles.biography}
            numberOfLines={4}
          >
            {item.biography}
          </Text>
        ) : null}

        {item.patronage ? (
          <Text style={styles.meta}>
            Patronage: {item.patronage}
          </Text>
        ) : null}

        {item.country ? (
          <Text style={styles.meta}>
            Country: {item.country}
          </Text>
        ) : null}

        <TouchableOpacity
          style={styles.deleteButton}
          onPress={() =>
            deleteSaint(item.id)
          }
        >
          <Ionicons
            name="trash-outline"
            size={18}
            color="#fff"
          />

          <Text style={styles.deleteText}>
            Delete
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
          Loading saints...
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={filtered}
        keyExtractor={(item) =>
          item.id.toString()
        }
        renderItem={renderSaint}
        showsVerticalScrollIndicator={false}
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
        ListHeaderComponent={
          <>
            {/* HEADER */}
            <View style={styles.header}>
              <View style={styles.headerText}>
                <Text style={styles.title}>
                  Saints Management
                </Text>

                <Text style={styles.subtitle}>
                  Manage saints and feast-day information
                </Text>
              </View>

              <TouchableOpacity
                style={styles.addIcon}
                onPress={() =>
                  setShowAddForm(
                    (current) => !current
                  )
                }
              >
                <Ionicons
                  name={
                    showAddForm
                      ? "close"
                      : "add"
                  }
                  size={25}
                  color="#fff"
                />
              </TouchableOpacity>
            </View>

            {/* SEARCH */}
            <View style={styles.searchBox}>
              <Ionicons
                name="search"
                size={20}
                color="#777"
              />

              <TextInput
                style={styles.search}
                placeholder="Search saints..."
                placeholderTextColor="#999"
                value={search}
                onChangeText={setSearch}
              />

              {search.length > 0 && (
                <TouchableOpacity
                  onPress={() => setSearch("")}
                >
                  <Ionicons
                    name="close-circle"
                    size={20}
                    color="#999"
                  />
                </TouchableOpacity>
              )}
            </View>

            {/* ADD FORM */}
            {showAddForm && (
              <View style={styles.form}>
                <Text style={styles.formTitle}>
                  Add Saint
                </Text>

                <TextInput
                  style={styles.input}
                  placeholder="Saint name"
                  placeholderTextColor="#999"
                  value={name}
                  onChangeText={setName}
                />

                <TextInput
                  style={styles.input}
                  placeholder="Feast date (YYYY-MM-DD)"
                  placeholderTextColor="#999"
                  value={feastDate}
                  onChangeText={setFeastDate}
                />

                <TextInput
                  style={styles.input}
                  placeholder="Country"
                  placeholderTextColor="#999"
                  value={country}
                  onChangeText={setCountry}
                />

                <TextInput
                  style={styles.input}
                  placeholder="Patronage"
                  placeholderTextColor="#999"
                  value={patronage}
                  onChangeText={setPatronage}
                />

                <TextInput
                  style={[
                    styles.input,
                    styles.textArea,
                  ]}
                  placeholder="Short description"
                  placeholderTextColor="#999"
                  multiline
                  textAlignVertical="top"
                  value={description}
                  onChangeText={setDescription}
                />

                <TextInput
                  style={[
                    styles.input,
                    styles.largeTextArea,
                  ]}
                  placeholder="Biography"
                  placeholderTextColor="#999"
                  multiline
                  textAlignVertical="top"
                  value={biography}
                  onChangeText={setBiography}
                />

                <Text style={styles.rankLabel}>
                  Liturgical Rank
                </Text>

                <View style={styles.rankRow}>
                  {[
                    "Memorial",
                    "Feast",
                    "Solemnity",
                    "Optional Memorial",
                  ].map((item) => (
                    <TouchableOpacity
                      key={item}
                      style={[
                        styles.rankChip,
                        rank === item &&
                          styles.rankActive,
                      ]}
                      onPress={() =>
                        setRank(item)
                      }
                    >
                      <Text
                        style={[
                          styles.rankText,
                          rank === item &&
                            styles.rankTextActive,
                        ]}
                      >
                        {item}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>

                <TouchableOpacity
                  style={[
                    styles.saveButton,
                    saving &&
                      styles.disabledButton,
                  ]}
                  onPress={addSaint}
                  disabled={saving}
                >
                  {saving ? (
                    <ActivityIndicator color="#fff" />
                  ) : (
                    <>
                      <Ionicons
                        name="save-outline"
                        size={19}
                        color="#fff"
                      />

                      <Text
                        style={styles.saveText}
                      >
                        Save Saint
                      </Text>
                    </>
                  )}
                </TouchableOpacity>
              </View>
            )}

            <View style={styles.countRow}>
              <Text style={styles.count}>
                {filtered.length} saint
                {filtered.length === 1
                  ? ""
                  : "s"}
              </Text>
            </View>
          </>
        }
        ListEmptyComponent={
          <View style={styles.empty}>
            <MaterialCommunityIcons
              name="account-search-outline"
              size={55}
              color="#aaa"
            />

            <Text style={styles.emptyTitle}>
              No saints found
            </Text>

            <Text style={styles.emptyText}>
              Try another search or add a new
              saint.
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

  list: {
    paddingBottom: 35,
  },

  emptyContainer: {
    flexGrow: 1,
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
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 18,
  },

  headerText: {
    flex: 1,
    marginRight: 10,
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

  addIcon: {
    width: 45,
    height: 45,
    borderRadius: 23,
    backgroundColor: "#0B6623",
    alignItems: "center",
    justifyContent: "center",
  },

  searchBox: {
    height: 52,
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: "#E0E5E1",
    borderRadius: 13,
    paddingHorizontal: 14,
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 15,
  },

  search: {
    flex: 1,
    marginHorizontal: 10,
    color: "#222",
    fontSize: 15,
  },

  form: {
    backgroundColor: "#fff",
    borderRadius: 15,
    padding: 16,
    marginBottom: 17,
    borderWidth: 1,
    borderColor: "#E2E7E3",
  },

  formTitle: {
    fontSize: 20,
    fontWeight: "800",
    color: "#0B6623",
    marginBottom: 14,
  },

  input: {
    minHeight: 50,
    borderWidth: 1,
    borderColor: "#D9DED9",
    borderRadius: 11,
    paddingHorizontal: 13,
    paddingVertical: 11,
    backgroundColor: "#fff",
    fontSize: 15,
    color: "#222",
    marginBottom: 11,
  },

  textArea: {
    minHeight: 95,
  },

  largeTextArea: {
    minHeight: 160,
  },

  rankLabel: {
    fontWeight: "700",
    color: "#333",
    marginBottom: 8,
  },

  rankRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    marginBottom: 10,
  },

  rankChip: {
    paddingHorizontal: 11,
    paddingVertical: 8,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "#0B6623",
    marginRight: 7,
    marginBottom: 7,
  },

  rankActive: {
    backgroundColor: "#0B6623",
  },

  rankText: {
    color: "#0B6623",
    fontSize: 12,
    fontWeight: "700",
  },

  rankTextActive: {
    color: "#fff",
  },

  saveButton: {
    minHeight: 50,
    borderRadius: 11,
    backgroundColor: "#0B6623",
    justifyContent: "center",
    alignItems: "center",
    flexDirection: "row",
    marginTop: 5,
  },

  disabledButton: {
    opacity: 0.65,
  },

  saveText: {
    color: "#fff",
    fontWeight: "800",
    marginLeft: 7,
  },

  countRow: {
    marginBottom: 10,
  },

  count: {
    color: "#777",
    fontWeight: "600",
  },

  card: {
    backgroundColor: "#fff",
    borderRadius: 15,
    padding: 16,
    marginBottom: 13,
    borderWidth: 1,
    borderColor: "#E5EAE6",
  },

  cardTop: {
    flexDirection: "row",
    alignItems: "center",
  },

  iconCircle: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: "#EAF4ED",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 11,
  },

  cardHeading: {
    flex: 1,
  },

  saintName: {
    fontSize: 18,
    fontWeight: "800",
    color: "#222",
  },

  feastDate: {
    color: "#777",
    fontSize: 13,
    marginTop: 4,
  },

  tag: {
    alignSelf: "flex-start",
    backgroundColor: "#EAF4ED",
    borderRadius: 15,
    paddingHorizontal: 9,
    paddingVertical: 5,
    marginTop: 11,
  },

  tagText: {
    color: "#0B6623",
    fontSize: 11,
    fontWeight: "800",
  },

  description: {
    color: "#555",
    marginTop: 11,
    lineHeight: 20,
  },

  biography: {
    color: "#666",
    marginTop: 9,
    lineHeight: 20,
  },

  meta: {
    color: "#777",
    fontSize: 13,
    marginTop: 6,
  },

  deleteButton: {
    marginTop: 14,
    minHeight: 44,
    borderRadius: 10,
    backgroundColor: "#C62828",
    justifyContent: "center",
    alignItems: "center",
    flexDirection: "row",
  },

  deleteText: {
    color: "#fff",
    fontWeight: "800",
    marginLeft: 6,
  },

  empty: {
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 30,
    marginTop: 70,
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