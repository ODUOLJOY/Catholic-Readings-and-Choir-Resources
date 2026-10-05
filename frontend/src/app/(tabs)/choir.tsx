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
import { useLocalSearchParams } from "expo-router";
import { api } from "@/lib/api";
import { API_URL } from "@/config/api";
import { cacheResource } from "@/services/offlineStore";
import { favoriteService, Favorite } from "@/services/favoriteService";
import { ReportButton } from "@/components/ReportButton";
import { Ionicons } from "@expo/vector-icons";
import { canonicaliseCategory, CHOIR_CATEGORY_SECTIONS } from "@/config/choirCategories";
import { safeExternalUrl } from "@/lib/externalUrl";

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
  key_signature?: string;
  tempo?: string;
  duration?: string;
  voice_part?: string;
  parish_id?: number | null;
}

// Canonical 27 categories live in @/config/choirCategories. The "All" option
// below is a browse filter, not a category a resource can be tagged with, so
// it is kept here rather than in the shared config.
const ALL_FILTER = "All";

/**
 * Resolve a `?category=` param to a canonical label, or to the browse filter.
 *
 * An absent param, the literal "All", or a value that is not one of the 27
 * canonical categories all fall back to showing every resource, rather than
 * sending an unrecognised value to the API and rendering nothing.
 */
function resolveCategoryParam(value: string | undefined | null): string {
  if (!value) {
    return ALL_FILTER;
  }
  if (value.trim().toLowerCase() === ALL_FILTER.toLowerCase()) {
    return ALL_FILTER;
  }
  return canonicaliseCategory(value.trim()) ?? ALL_FILTER;
}

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

// Voices / parts for choral resources
const voiceParts = [
  "All Voices",
  "Soprano",
  "Alto",
  "Tenor",
  "Bass",
  "SATB",
];

// Common Western key signatures (ASCII sharp/flat spelling)
const keySignatures = [
  "All Keys",
  "C",
  "G",
  "D",
  "A",
  "E",
  "B",
  "F#",
  "Bb",
  "Eb",
  "Ab",
  "Db",
  "Gb",
  "F",
];

// Tempo / metre markings
const tempoMarkers = [
  "All Tempos",
  "Largo",
  "Andante",
  "Moderato",
  "Allegro",
  "Presto",
  "Slow",
  "Moderate",
  "Fast",
];

export default function Choir() {
  // Home's category grid and deep links navigate here with `?category=`. The
  // screen used to ignore this param entirely and always start on "All", so the
  // tap appeared to do nothing.
  const { category: categoryParam } = useLocalSearchParams<{ category?: string }>();

  const [resources, setResources] = useState<ChoirResource[]>([]);
  const [filtered, setFiltered] = useState<ChoirResource[]>([]);

  const [search, setSearch] = useState("");
  const [category, setCategory] = useState(() => resolveCategoryParam(categoryParam));
  const [season, setSeason] = useState("All Seasons");
  const [language, setLanguage] = useState("All Languages");
  const [fileType, setFileType] = useState("All Types");
  const [voicePart, setVoicePart] = useState("All Voices");
  const [keySignature, setKeySignature] = useState("All Keys");
  const [tempo, setTempo] = useState("All Tempos");

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [favorites, setFavorites] = useState<Favorite[]>([]);

  const [showSeasons, setShowSeasons] = useState(false);
  const [showLanguages, setShowLanguages] = useState(false);
  const [showFileTypes, setShowFileTypes] = useState(false);
  const [showVoicePart, setShowVoicePart] = useState(false);
  const [showKeySignature, setShowKeySignature] = useState(false);
  const [showTempo, setShowTempo] = useState(false);

  useEffect(() => {
    loadFavorites();
  }, []);

  // Keep the filter in step with the param. This covers returning to an already
  // mounted tab screen, where only the param changes and state would otherwise
  // keep the previous filter.
  useEffect(() => {
    void Promise.resolve().then(() => setCategory(resolveCategoryParam(categoryParam)));
  }, [categoryParam]);

  async function loadFavorites() {
    try {
        const favs = await favoriteService.getFavorites();
        setFavorites(favs);
    } catch (error) {
        console.error("Failed to load favorites", error);
    }
  }

  async function toggleFavorite(item: ChoirResource) {
    const isFavorited = favorites.some(f => f.resource_type === 'choir' && f.target_resource_id === item.id);
    const favorite = favorites.find(f => f.resource_type === 'choir' && f.target_resource_id === item.id);
    
    try {
      if (isFavorited && favorite) {
        await favoriteService.deleteFavorite(favorite.id);
        setFavorites(favorites.filter(f => f.id !== favorite.id));
      } else {
        const newFav = await favoriteService.createFavorite('choir', item.id);
        setFavorites([...favorites, newFav]);
      }
    } catch (error: any) {
      Alert.alert("Error", "Could not toggle favorite");
    }
  }

  // Server-side fetch whenever a server-side facet (or text search) changes.
  useEffect(() => {
    loadResources();
  }, [
    search,
    category,
    language,
    season,
    voicePart,
    keySignature,
    tempo,
  ]);

  // Client-side post-filter applied to the server result set (file_type only).
  useEffect(() => {
    filterResources();
  }, [resources, fileType]);

  async function loadResources() {
    try {
      setLoading(true);

      const params: Record<string, string> = {};
      if (search.trim()) {
        params.query = search.trim();
      }
      if (category !== ALL_FILTER) {
        params.category = category;
      }
      if (language !== "All Languages") {
        params.language = language;
      }
      if (season !== "All Seasons") {
        params.season = season;
      }
      if (voicePart !== "All Voices") {
        params.voice_part = voicePart;
      }
      if (keySignature !== "All Keys") {
        params.key_signature = keySignature;
      }
      if (tempo !== "All Tempos") {
        params.tempo = tempo;
      }

      const response = await api.get("/api/choir/", { params });

      const data =
        Array.isArray(response.data)
          ? response.data
          : response.data?.items || [];

      setResources(data);
    } catch (error) {
      Alert.alert("Error", "Unable to load choir resources.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  // Client-side post-filter. All database-capable facets (search, category,
  // season, language, voice part, key signature and tempo) are applied by
  // loadResources via server-side query parameters. Only the file-type facet
  // remains here because file_type stores a raw extension (e.g. mp3) and is
  // matched with a substring include for parity with prior behaviour.
  function filterResources() {
    let data = [...resources];

    if (fileType !== "All Types") {
      const ft = fileType.toLowerCase();
      data = data.filter((item) =>
        item.file_type?.toLowerCase().includes(ft)
      );
    }

    setFiltered(data);
  }

  async function refresh() {
    setRefreshing(true);
    await loadResources();
  }

  async function openFile(resource: ChoirResource) {
    if (!resource.file_url) {
      Alert.alert(
        "Unavailable",
        "This resource does not have a file."
      );
      return;
    }

    try {
      // `safeExternalUrl` refuses any scheme other than http(s). `new URL` alone
      // would happily accept `file:`, `data:` or an app deep link stored in
      // `file_url` and hand it to the OS handler.
      const directUrl =
        resource.parish_id == null
          ? safeExternalUrl(resource.file_url, API_URL)
          : null;

      const fileUri =
        resource.parish_id == null
          ? directUrl
          : await cacheResource(resource);

      if (!fileUri) {
        Alert.alert(
          "Unavailable",
          "This resource does not have a usable link."
        );
        return;
      }

      const supported =
        await Linking.canOpenURL(fileUri);

      if (!supported) {
        Alert.alert(
          "Cannot Open",
          "This resource cannot be opened on this device."
        );
        return;
      }

      await Linking.openURL(fileUri);
    } catch {
      Alert.alert(
        "Error",
        "Unable to open this resource."
      );
    }
  }

  async function downloadResource(resource: ChoirResource) {
    try {
      await cacheResource(resource);
      await api.post(`/api/downloads/${resource.id}`);
      Alert.alert("Downloaded", "This resource is available offline and recorded in your downloads.");
    } catch (error: any) {
      Alert.alert(
        "Download Failed",
        error?.response?.data?.detail ||
          "The file could not be downloaded. Check your connection and try again."
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
          <TouchableOpacity onPress={() => toggleFavorite(item)}>
            <Ionicons name={favorites.some(f => f.resource_type === 'choir' && f.target_resource_id === item.id) ? "bookmark" : "bookmark-outline"} size={24} color="#0B6623" />
          </TouchableOpacity>
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

          {item.voice_part ? (
            <Text style={styles.tag}>
              {item.voice_part}
            </Text>
          ) : null}
        </View>

        {item.composer ? (
          <Text style={styles.metadata}>
            Composer: {item.composer}
          </Text>
        ) : null}

        {item.key_signature ? (
          <Text style={styles.metadata}>
            Key: {item.key_signature}
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
            openFile(item)
          }
        >
          <Text style={styles.buttonText}>
            Open Resource
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.secondaryButton}
          onPress={() => downloadResource(item)}
        >
          <Text style={styles.secondaryButtonText}>
            Save Download
          </Text>
        </TouchableOpacity>
        <ReportButton resourceType="choir" resourceId={item.id} />
      </View>
    );
  }

  function closeAllDropdowns() {
    setShowSeasons(false);
    setShowLanguages(false);
    setShowFileTypes(false);
    setShowVoicePart(false);
    setShowKeySignature(false);
    setShowTempo(false);
  }

  function toggleDropdown(
    isOpen: boolean,
    setIsOpen: (isOpen: boolean) => void
  ) {
    if (isOpen) {
      setIsOpen(false);
    } else {
      closeAllDropdowns();
      setIsOpen(true);
    }
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

      <ScrollView
        style={styles.categoriesScroll}
        contentContainerStyle={styles.categoriesContent}
        showsVerticalScrollIndicator={false}
      >
        {/* "All" is a browse filter, not a resource category. It sits above the
            three sections so users can clear the category filter in one tap. */}
        <View style={styles.categoryRow}>
          <TouchableOpacity
            style={[
              styles.categoryButton,
              category === ALL_FILTER && styles.categoryActive,
            ]}
            onPress={() => setCategory(ALL_FILTER)}
          >
            <Text
              style={[
                styles.categoryText,
                category === ALL_FILTER && styles.categoryTextActive,
              ]}
            >
              {ALL_FILTER}
            </Text>
          </TouchableOpacity>
        </View>

        {CHOIR_CATEGORY_SECTIONS.map((section) => (
          <View key={section.title} style={styles.categorySection}>
            <Text style={styles.categorySectionTitle}>
              {section.title}
            </Text>
            <View style={styles.categoryRow}>
              {section.categories.map((item) => {
                const active = category === item;
                return (
                  <TouchableOpacity
                    key={item}
                    style={[
                      styles.categoryButton,
                      active && styles.categoryActive,
                    ]}
                    onPress={() => setCategory(item)}
                  >
                    <Text
                      style={[
                        styles.categoryText,
                        active && styles.categoryTextActive,
                      ]}
                    >
                      {item}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>
        ))}
      </ScrollView>

      <View style={styles.filterRow}>
        {renderFilterButton(
          season,
          season !== "All Seasons",
          () => toggleDropdown(showSeasons, setShowSeasons)
        )}

        {renderFilterButton(
          language,
          language !== "All Languages",
          () => toggleDropdown(showLanguages, setShowLanguages)
        )}

        {renderFilterButton(
          fileType,
          fileType !== "All Types",
          () => toggleDropdown(showFileTypes, setShowFileTypes)
        )}

        {renderFilterButton(
          voicePart,
          voicePart !== "All Voices",
          () => toggleDropdown(showVoicePart, setShowVoicePart)
        )}

        {renderFilterButton(
          keySignature,
          keySignature !== "All Keys",
          () => toggleDropdown(showKeySignature, setShowKeySignature)
        )}

        {renderFilterButton(
          tempo,
          tempo !== "All Tempos",
          () => toggleDropdown(showTempo, setShowTempo)
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

      {showVoicePart && (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.dropdown}
        >
          {voiceParts.map((item) => (
            <TouchableOpacity
              key={item}
              style={[
                styles.dropdownItem,
                voicePart === item && styles.dropdownActive,
              ]}
              onPress={() => {
                setVoicePart(item);
                setShowVoicePart(false);
              }}
            >
              <Text
                style={
                  voicePart === item
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

      {showKeySignature && (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.dropdown}
        >
          {keySignatures.map((item) => (
            <TouchableOpacity
              key={item}
              style={[
                styles.dropdownItem,
                keySignature === item && styles.dropdownActive,
              ]}
              onPress={() => {
                setKeySignature(item);
                setShowKeySignature(false);
              }}
            >
              <Text
                style={
                  keySignature === item
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

      {showTempo && (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.dropdown}
        >
          {tempoMarkers.map((item) => (
            <TouchableOpacity
              key={item}
              style={[
                styles.dropdownItem,
                tempo === item && styles.dropdownActive,
              ]}
              onPress={() => {
                setTempo(item);
                setShowTempo(false);
              }}
            >
              <Text
                style={
                  tempo === item
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

        {(category !== ALL_FILTER ||
          season !== "All Seasons" ||
          language !== "All Languages" ||
          fileType !== "All Types" ||
          voicePart !== "All Voices" ||
          keySignature !== "All Keys" ||
          tempo !== "All Tempos" ||
          search.trim().length > 0) && (
          <TouchableOpacity
            onPress={() => {
              setCategory(ALL_FILTER);
              setSeason("All Seasons");
              setLanguage("All Languages");
              setFileType("All Types");
              setVoicePart("All Voices");
              setKeySignature("All Keys");
              setTempo("All Tempos");
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
              Try another category, season, voice part,
              key signature, tempo, language, or search term.
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

  categoriesScroll: {
    marginBottom: 15,
  },

  categoriesContent: {
    paddingBottom: 4,
  },

  categorySection: {
    marginTop: 10,
  },

  categorySectionTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#0B6623",
    textTransform: "uppercase",
    letterSpacing: 0.4,
    marginBottom: 8,
  },

  categoryRow: {
    flexDirection: "row",
    flexWrap: "wrap",
  },

  categoryButton: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "#0B6623",
    marginRight: 8,
    marginBottom: 8,
    backgroundColor: "#fff",
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

  secondaryButton: {
    borderWidth: 1,
    borderColor: "#0B6623",
    padding: 12,
    borderRadius: 10,
    marginTop: 8,
  },

  secondaryButtonText: {
    color: "#0B6623",
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