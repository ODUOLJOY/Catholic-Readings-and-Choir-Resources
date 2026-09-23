import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
  Linking,
} from "react-native";
import { api } from "@/lib/api";

interface ChoirResource {
  id: number;
  title: string;
  category: string;
  description: string;
  file_type: string;
  file_url: string;
  created_at: string;

  // Optional fields supported by the expanded backend
  language?: string;
  season?: string;
  composer?: string;
  key?: string;
  tempo?: string;
  duration?: string;
  choir_voice?: string;
}

const categories = [
  "All",

  // Mass
  "Entrance",
  "Kyrie Eleison",
  "Gloria",
  "Responsorial Psalm",
  "Gospel Acclamation",
  "Sadaka",
  "Offertory",
  "Sanctus",
  "Holy Holy",
  "Memorial Acclamation",
  "Great Amen",
  "Agnus Dei",
  "Lamb of God",
  "Communion",
  "Thanksgiving",
  "Exit",
  "Recessional",

  // Liturgical seasons
  "Advent",
  "Christmas",
  "Lent",
  "Holy Week",
  "Triduum",
  "Easter",
  "Pentecost",
  "Ordinary Time",

  // Marian
  "Marian",
  "Our Lady",
  "Rosary",
  "Ave Maria",
  "Marian Feasts",

  // Sacraments and occasions
  "Wedding",
  "Funeral",
  "Baptism",
  "Confirmation",
  "First Holy Communion",
  "Ordination",
  "Anointing of the Sick",

  // Eucharistic / devotional
  "Eucharistic",
  "Adoration",
  "Benediction",
  "Divine Mercy",
  "Praise and Worship",

  // Saints and feasts
  "Saints",
  "All Saints",
  "All Souls",
  "Feast Day",

  // Christmas-related
  "Carols",
  "Epiphany",
  "Holy Family",
  "Christ the King",

  // Other
  "Children",
  "Youth",
  "Choir Practice",
  "Gregorian Chant",
  "Latin Chant",
  "Swahili",
  "English",
  "Latin",
  "Other",
];

const seasons = [
  "All Seasons",
  "Advent",
  "Christmas",
  "Lent",
  "Holy Week",
  "Triduum",
  "Easter",
  "Pentecost",
  "Ordinary Time",
];

const languages = [
  "All Languages",
  "English",
  "Swahili",
  "Latin",
  "Other",
];

const fileTypes = [
  "All Types",
  "Audio",
  "PDF",
  "Video",
  "Lyrics",
  "Sheet Music",
];

export default function Choir() {
  const [resources, setResources] = useState<ChoirResource[]>([]);
  const [filtered, setFiltered] = useState<ChoirResource[]>([]);

  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All");
  const [season, setSeason] = useState("All Seasons");
  const [language, setLanguage] = useState("All Languages");
  const [fileType, setFileType] = useState("All Types");

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [showSeasons, setShowSeasons] = useState(false);
  const [showLanguages, setShowLanguages] = useState(false);
  const [showFileTypes, setShowFileTypes] = useState(false);

  useEffect(() => {
    loadResources();
  }, []);

  useEffect(() => {
    filterResources();
  }, [
    search,
    category,
    season,
    language,
    fileType,
    resources,
  ]);

  async function loadResources() {
    try {
      setLoading(true);

      const response = await api.get("/api/choir/");

      setResources(
        Array.isArray(response.data)
          ? response.data
          : response.data?.items || []
      );
    } catch (error) {
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
        (item) =>
          item.category?.toLowerCase() ===
          category.toLowerCase()
      );
    }

    if (season !== "All Seasons") {
      data = data.filter(
        (item) =>
          item.season?.toLowerCase() ===
            season.toLowerCase() ||
          item.category?.toLowerCase() ===
            season.toLowerCase()
      );
    }

    if (language !== "All Languages") {
      data = data.filter(
        (item) =>
          item.language?.toLowerCase() ===
          language.toLowerCase()
      );
    }

    if (fileType !== "All Types") {
      data = data.filter((item) =>
        item.file_type
          ?.toLowerCase()
          .includes(fileType.toLowerCase())
      );
    }

    if (search.trim()) {
      const query = search.trim().toLowerCase();

      data = data.filter((item) => {
        return (
          item.title?.toLowerCase().includes(query) ||
          item.category?.toLowerCase().includes(query) ||
          item.description
            ?.toLowerCase()
            .includes(query) ||
          item.composer
            ?.toLowerCase()
            .includes(query) ||
          item.language
            ?.toLowerCase()
            .includes(query) ||
          item.season
            ?.toLowerCase()
            .includes(query)
        );
      });
    }

    setFiltered(data);
  }

  async function refresh() {
    setRefreshing(true);
    await loadResources();
  }

  async function openFile(url: string) {
    if (!url) {
      Alert.alert(
        "Unavailable",
        "This resource does not have a file."
      );
      return;
    }

    try {
      const supported =
        await Linking.canOpenURL(url);

      if (!supported) {
        Alert.alert(
          "Cannot Open",
          "This resource cannot be opened on this device."
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

  function getFileIcon(fileType: string) {
    const type = fileType?.toLowerCase() || "";

    if (type.includes("audio")) return "🎵";
    if (type.includes("video")) return "🎬";
    if (type.includes("pdf")) return "📄";
    if (type.includes("sheet")) return "🎼";
    if (type.includes("lyrics")) return "📝";

    return "🎶";
  }

  function renderItem({
    item,
  }: {
    item: ChoirResource;
  }) {
    return (
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <Text style={styles.icon}>
            {getFileIcon(item.file_type)}
          </Text>

          <View style={styles.titleContainer}>
            <Text style={styles.songTitle}>
              {item.title}
            </Text>

            <Text style={styles.category}>
              {item.category}
            </Text>
          </View>
        </View>

        {item.description ? (
          <Text style={styles.description}>
            {item.description}
          </Text>
        ) : null}

        <View style={styles.tags}>
          <Text style={styles.tag}>
            {item.file_type?.toUpperCase()}
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

          {item.choir_voice ? (
            <Text style={styles.tag}>
              {item.choir_voice}
            </Text>
          ) : null}
        </View>

        {item.composer ? (
          <Text style={styles.metadata}>
            Composer: {item.composer}
          </Text>
        ) : null}

        {item.key ? (
          <Text style={styles.metadata}>
            Key: {item.key}
          </Text>
        ) : null}

        {item.tempo ? (
          <Text style={styles.metadata}>
            Tempo: {item.tempo}
          </Text>
        ) : null}

        {item.duration ? (
          <Text style={styles.metadata}>
            Duration: {item.duration}
          </Text>
        ) : null}

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

  function renderFilterButton(
    label: string,
    active: boolean,
    onPress: () => void
  ) {
    return (
      <TouchableOpacity
        style={[
          styles.filterButton,
          active && styles.filterButtonActive,
        ]}
        onPress={onPress}
      >
        <Text
          style={[
            styles.filterText,
            active && styles.filterTextActive,
          ]}
        >
          {label}
        </Text>
      </TouchableOpacity>
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
          Loading choir resources...
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>
        Choir Resources
      </Text>

      <Text style={styles.subtitle}>
        Catholic Mass Songs, Hymns & Choir Resources
      </Text>

      <TextInput
        placeholder="Search songs, hymns, composers..."
        placeholderTextColor="#888"
        style={styles.search}
        value={search}
        onChangeText={setSearch}
      />

      <Text style={styles.sectionTitle}>
        Mass & Song Categories
      </Text>

      <FlatList
        horizontal
        showsHorizontalScrollIndicator={false}
        data={categories}
        keyExtractor={(item) => item}
        style={styles.categoryList}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={[
              styles.categoryButton,
              category === item &&
                styles.categoryActive,
            ]}
            onPress={() => setCategory(item)}
          >
            <Text
              style={[
                styles.categoryText,
                category === item &&
                  styles.categoryTextActive,
              ]}
            >
              {item}
            </Text>
          </TouchableOpacity>
        )}
      />

      <View style={styles.filterRow}>
        {renderFilterButton(
          season,
          season !== "All Seasons",
          () => {
            setShowSeasons(!showSeasons);
            setShowLanguages(false);
            setShowFileTypes(false);
          }
        )}

        {renderFilterButton(
          language,
          language !== "All Languages",
          () => {
            setShowLanguages(!showLanguages);
            setShowSeasons(false);
            setShowFileTypes(false);
          }
        )}

        {renderFilterButton(
          fileType,
          fileType !== "All Types",
          () => {
            setShowFileTypes(!showFileTypes);
            setShowSeasons(false);
            setShowLanguages(false);
          }
        )}
      </View>

      {showSeasons && (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.dropdown}
        >
          {seasons.map((item) => (
            <TouchableOpacity
              key={item}
              style={[
                styles.dropdownItem,
                season === item &&
                  styles.dropdownActive,
              ]}
              onPress={() => {
                setSeason(item);
                setShowSeasons(false);
              }}
            >
              <Text
                style={
                  season === item
                    ? styles.dropdownActiveText
                    : styles.dropdownText
                }
              >
                {item}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      )}

      {showLanguages && (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.dropdown}
        >
          {languages.map((item) => (
            <TouchableOpacity
              key={item}
              style={[
                styles.dropdownItem,
                language === item &&
                  styles.dropdownActive,
              ]}
              onPress={() => {
                setLanguage(item);
                setShowLanguages(false);
              }}
            >
              <Text
                style={
                  language === item
                    ? styles.dropdownActiveText
                    : styles.dropdownText
                }
              >
                {item}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      )}

      {showFileTypes && (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.dropdown}
        >
          {fileTypes.map((item) => (
            <TouchableOpacity
              key={item}
              style={[
                styles.dropdownItem,
                fileType === item &&
                  styles.dropdownActive,
              ]}
              onPress={() => {
                setFileType(item);
                setShowFileTypes(false);
              }}
            >
              <Text
                style={
                  fileType === item
                    ? styles.dropdownActiveText
                    : styles.dropdownText
                }
              >
                {item}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      )}

      <View style={styles.resultHeader}>
        <Text style={styles.resultCount}>
          {filtered.length} resource
          {filtered.length === 1 ? "" : "s"}
        </Text>

        {(category !== "All" ||
          season !== "All Seasons" ||
          language !== "All Languages" ||
          fileType !== "All Types" ||
          search.trim()) && (
          <TouchableOpacity
            onPress={() => {
              setCategory("All");
              setSeason("All Seasons");
              setLanguage("All Languages");
              setFileType("All Types");
              setSearch("");
            }}
          >
            <Text style={styles.clear}>
              Clear Filters
            </Text>
          </TouchableOpacity>
        )}
      </View>

      <FlatList
        data={filtered}
        keyExtractor={(item) =>
          item.id.toString()
        }
        renderItem={renderItem}
        contentContainerStyle={
          filtered.length === 0
            ? styles.emptyContainer
            : undefined
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
              🎵
            </Text>

            <Text style={styles.empty}>
              No choir resources found.
            </Text>

            <Text style={styles.emptyHint}>
              Try another category, season,
              language, or search term.
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
    paddingTop: 15,
  },

  loading: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#fff",
  },

  loadingText: {
    marginTop: 12,
    color: "#666",
  },

  title: {
    fontSize: 28,
    fontWeight: "bold",
    color: "#0B6623",
  },

  subtitle: {
    color: "#666",
    marginTop: 4,
    marginBottom: 15,
  },

  search: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    marginBottom: 15,
    backgroundColor: "#fafafa",
    fontSize: 15,
  },

  sectionTitle: {
    fontSize: 16,
    fontWeight: "700",
    marginBottom: 10,
    color: "#333",
  },

  categoryList: {
    marginBottom: 15,
    minHeight: 42,
  },

  categoryButton: {
    paddingHorizontal: 15,
    paddingVertical: 9,
    borderRadius: 25,
    borderWidth: 1,
    borderColor: "#0B6623",
    marginRight: 8,
    height: 40,
    justifyContent: "center",
  },

  categoryActive: {
    backgroundColor: "#0B6623",
  },

  categoryText: {
    color: "#0B6623",
    fontWeight: "600",
  },

  categoryTextActive: {
    color: "#fff",
  },

  filterRow: {
    flexDirection: "row",
    marginBottom: 10,
  },

  filterButton: {
    borderWidth: 1,
    borderColor: "#ccc",
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginRight: 8,
    backgroundColor: "#fff",
  },

  filterButtonActive: {
    backgroundColor: "#0B6623",
    borderColor: "#0B6623",
  },

  filterText: {
    color: "#444",
    fontSize: 13,
    fontWeight: "600",
  },

  filterTextActive: {
    color: "#fff",
  },

  dropdown: {
    marginBottom: 10,
  },

  dropdownItem: {
    paddingHorizontal: 13,
    paddingVertical: 9,
    borderRadius: 18,
    backgroundColor: "#f1f1f1",
    marginRight: 8,
  },

  dropdownActive: {
    backgroundColor: "#0B6623",
  },

  dropdownText: {
    color: "#333",
  },

  dropdownActiveText: {
    color: "#fff",
    fontWeight: "700",
  },

  resultHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 10,
  },

  resultCount: {
    color: "#666",
    fontWeight: "600",
  },

  clear: {
    color: "#C62828",
    fontWeight: "700",
  },

  card: {
    backgroundColor: "#fafafa",
    padding: 16,
    borderRadius: 14,
    marginBottom: 15,
    borderWidth: 1,
    borderColor: "#eee",

    elevation: 2,
  },

  cardHeader: {
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

  songTitle: {
    fontSize: 19,
    fontWeight: "700",
    color: "#222",
  },

  category: {
    color: "#0B6623",
    marginTop: 4,
    fontWeight: "700",
  },

  description: {
    marginTop: 12,
    marginBottom: 10,
    color: "#555",
    lineHeight: 20,
  },

  tags: {
    flexDirection: "row",
    flexWrap: "wrap",
    marginBottom: 8,
  },

  tag: {
    backgroundColor: "#e9f3ec",
    color: "#0B6623",
    paddingHorizontal: 9,
    paddingVertical: 5,
    borderRadius: 15,
    marginRight: 6,
    marginBottom: 5,
    fontSize: 11,
    fontWeight: "700",
  },

  metadata: {
    color: "#666",
    marginTop: 3,
    fontSize: 13,
  },

  button: {
    backgroundColor: "#0B6623",
    padding: 13,
    borderRadius: 10,
    marginTop: 14,
  },

  buttonText: {
    color: "#fff",
    textAlign: "center",
    fontWeight: "700",
  },

  emptyContainer: {
    flexGrow: 1,
  },

  emptyBox: {
    alignItems: "center",
    marginTop: 60,
    paddingHorizontal: 30,
  },

  emptyIcon: {
    fontSize: 45,
    marginBottom: 12,
  },

  empty: {
    textAlign: "center",
    color: "#888",
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