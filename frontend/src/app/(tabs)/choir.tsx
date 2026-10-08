/**
 * Choir library.
 *
 * Replaces a single screen of filter chips above a flat list. The page is now
 * built around what a choir actually does on a Tuesday: find out what the
 * Church is celebrating, pick the music for the parts of Mass that are still
 * missing, and reach the practice material. So the order is
 *
 *   hero -> today's celebration -> search -> the 27 categories -> prepare for
 *   Mass -> featured -> practice -> recently added -> recently loved
 *
 * Everything on it is a real answer from the API. The category counts come from
 * `GET /api/choir/categories`, the shelves from `GET /api/choir/`, the
 * celebration from `GET /api/v1/liturgy/today`. When a service is unreachable
 * the affected block says so and offers a retry -- it never substitutes
 * placeholder resources, counts or a guessed season.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";

import { ChoirResourceCard } from "@/components/choir/ChoirResourceCard";
import { useChoirPlayer } from "@/components/choir/ChoirPlayerProvider";
import {
  ChoirRadius,
  ChoirShadow,
  ChoirSpace,
  ChoirTheme,
  ChoirType,
  MaxChoirContentWidth,
  MinTouchTarget,
  liturgicalAccent,
} from "@/constants/choirTheme";
import { useLiturgicalToday } from "@/hooks/useLiturgicalToday";
import { favoriteService, type Favorite } from "@/services/favoriteService";
import { listCachedResources } from "@/services/offlineStore";
import {
  fetchCategories,
  fetchResources,
  MASS_ORDINARY_ORDER,
  normaliseResource,
  type ChoirCategoriesResponse,
  type ChoirResource,
  type ChoirSort,
} from "@/services/choirService";
import { classifyRequestFailure } from "@/lib/requestFailure";
import { fetchConcurrent } from "@/lib/api";
import { ErrorState } from "@/components/ScreenStates";
import { canonicaliseCategory } from "@/config/choirCategories";
import AsyncStorage from "@react-native-async-storage/async-storage";

type Shelf = {
  key: string;
  title: string;
  subtitle?: string;
  resources: ChoirResource[];
  error?: string;
  loading?: boolean;
};

const PRACTICE_CATEGORY = "Choir Practice";
/** Icons for the three grouped sections. */
const SECTION_ICON: Record<string, React.ComponentProps<typeof Ionicons>["name"]> = {
  "Mass Ordinary and Celebration Songs": "musical-notes",
  "Liturgical Seasons": "calendar",
  "Other Choir Categories": "heart",
};

/**
 * An icon per category, chosen from the label. This is presentation only -- it
 * never decides what a category contains or whether a resource exists.
 */
function iconForCategory(category: string): React.ComponentProps<typeof Ionicons>["name"] {
  if (MASS_ORDINARY_ORDER.includes(category as (typeof MASS_ORDINARY_ORDER)[number])) {
    return "musical-notes";
  }
  if (category === "Marian" || category === "Rosary") {
    return "flower";
  }
  if (category === "Wedding" || category === "Baptism" || category === "Funeral") {
    return "ribbon";
  }
  if (category === "Latin") {
    return "language";
  }
  if (category === "Choir Practice") {
    return "school";
  }
  if (category === "Saints") {
    return "star";
  }
  if (category === "Benediction" || category === "Adoration") {
    return "sunny";
  }
  return "folder-open";
}

export default function Choir() {
  const { category: categoryParam } = useLocalSearchParams<{ category?: string }>();
  const router = useRouter();
  const { width } = useWindowDimensions();
  const isWide = width >= 900;
  const player = useChoirPlayer();

  const [categories, setCategories] = useState<ChoirCategoriesResponse | null>(null);
  const [categoriesError, setCategoriesError] = useState<string | null>(null);
  const [categoriesOffline, setCategoriesOffline] = useState(false);
  const [favorites, setFavorites] = useState<Favorite[]>([]);

  const [search, setSearch] = useState("");
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [sort, setSort] = useState<ChoirSort>("recent");

  const [initialLoading, setInitialLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [notice, setNotice] = useState<{ tone: "info" | "error"; message: string } | null>(null);
  const [searchResults, setSearchResults] = useState<ChoirResource[] | null>(null);
  const [searchBusy, setSearchBusy] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const liturgy = useLiturgicalToday();

  // Home's category grid deep-links here with `?category=`.
  useEffect(() => {
    const raw = typeof categoryParam === "string" ? categoryParam.trim() : "";
    // Home's category grid deep-links here with `?category=`. The label is
    // canonicalised first: an unrecognised or legacy value must fall back to
    // browsing everything rather than being sent to the API as-is, where an
    // unknown filter matches nothing and the page looks simply empty.
    const next = raw ? (canonicaliseCategory(raw) ?? null) : null;
    // Deferred into a microtask: this mirrors the rest of the app's navigation
    // param handling and keeps the state update out of the effect body.
    void Promise.resolve().then(() => setActiveCategory(next));
  }, [categoryParam]);

  const loadCategories = useCallback(async () => {
    const result = await fetchCategories();
    if (result.kind === "ok") {
      setCategories(result.data);
      setCategoriesError(null);
      setCategoriesOffline(result.offline === true);
    } else {
      setCategoriesError(result.failure.message);
    }
  }, []);

  const loadFavorites = useCallback(async () => {
    // `getFavoritesOptional` never rejects: an anonymous visitor simply has no
    // bookmarks, which is not an error worth an alert.
    const favs = await favoriteService.getFavoritesOptional();
    setFavorites(favs);
  }, []);

  useEffect(() => {
    void (async () => {
      await Promise.all([loadCategories(), loadFavorites()]);
      setInitialLoading(false);
    })();
  }, [loadCategories, loadFavorites]);

  const isFavorited = useCallback(
    (id: number) =>
      favorites.some((f) => f.resource_type === "choir" && f.target_resource_id === id),
    [favorites],
  );

  const toggleFavorite = useCallback(
    async (resource: ChoirResource) => {
      const existing = favorites.find(
        (f) => f.resource_type === "choir" && f.target_resource_id === resource.id,
      );
      try {
        if (existing) {
          await favoriteService.deleteFavorite(existing.id);
          setFavorites((current) => current.filter((f) => f.id !== existing.id));
          setNotice({ tone: "info", message: `Removed “${resource.title}” from bookmarks.` });
        } else {
          const created = await favoriteService.createFavorite("choir", resource.id);
          setFavorites((current) => [...current, created]);
          setNotice({ tone: "info", message: `Saved “${resource.title}” to bookmarks.` });
        }
      } catch (error) {
        const failure = classifyRequestFailure(error, {
          fallbackNotFound: "That resource is not available.",
          fallbackMessage: "Could not reach the server. Check your connection and try again.",
        });
        // Reported in place. Navigating away here -- to /login, or worse to an
        // unrelated screen -- would throw away the member's place in the library
        // and hide the only actionable message. A signed-out visitor gets told
        // to sign in; the sign-in link is a separate, deliberate action.
        setNotice({
          tone: "error",
          message:
            failure.kind === "unauthorized"
              ? "Sign in to bookmark choir resources."
              : failure.message,
        });
      }
    },
    [favorites],
  );

  // --- Shelves -------------------------------------------------------------
  // Each shelf is one bounded request. A shelf that fails renders its own
  // message and retry; the rest of the page stays usable.

  const [massShelf, setMassShelf] = useState<Shelf | null>(null);
  const [featuredShelf, setFeaturedShelf] = useState<Shelf | null>(null);
  const [practiceShelf, setPracticeShelf] = useState<Shelf | null>(null);
  const [recentShelf, setRecentShelf] = useState<Shelf | null>(null);
  const [seasonShelf, setSeasonShelf] = useState<Shelf | null>(null);
  const [offlineShelf, setOfflineShelf] = useState<Shelf | null>(null);

  /**
   * Files this device holds a local copy of.
   *
   * Built from `offlineStore` rather than from a cached API list on purpose:
   * the library endpoint is permission-scoped, so a stored list could show a
   * member something their account no longer has access to. These are items
   * the member explicitly saved.
   */
  const loadOfflineShelf = useCallback(async () => {
    const entries = await listCachedResources();
    if (!entries.length) {
      setOfflineShelf(null);
      return;
    }
    setOfflineShelf({
      key: "offline",
      title: "Saved on this device",
      subtitle: "Plays without a connection",
      resources: entries.map((entry) =>
        normaliseResource({
          id: entry.id,
          title: entry.title,
          file_url: entry.fileUrl,
          is_downloaded: true,
        }),
      ),
    });
  }, []);

  const loadShelf = useCallback(
    async (
      set: (shelf: Shelf) => void,
      key: string,
      title: string,
      subtitle: string | undefined,
      filters: Parameters<typeof fetchResources>[0],
    ) => {
      set({ key, title, subtitle, resources: [], loading: true });
      const result = await fetchResources(filters);
      if (result.kind === "ok") {
        set({ key, title, subtitle, resources: result.data });
      } else {
        set({ key, title, subtitle, resources: [], error: result.failure.message });
      }
    },
    [],
  );

  const loadAllShelves = useCallback(async () => {
    const jobs: Promise<void>[] = [
      loadOfflineShelf(),
      loadShelf(setFeaturedShelf, "featured", "Most loved by choirs", "Ranked by real downloads", {
        sort: "popular",
        limit: 6,
      }),
      loadShelf(setRecentShelf, "recent", "Recently added", undefined, {
        sort: "recent",
        limit: 8,
      }),
      loadShelf(setMassShelf, "mass", "Prepare for Mass", "The ordinary, in the order it is sung", {
        categories: [...MASS_ORDINARY_ORDER],
        sort: "title",
      }),
      loadShelf(setPracticeShelf, "practice", "Choir practice", "Rehearsal and formation material", {
        category: PRACTICE_CATEGORY,
        sort: "recent",
        limit: 4,
      }),
    ];

    // Only ask for a season shelf once the liturgy service has actually named a
    // season the library carries. This is not a hard-coded season.
    const seasonCategory = liturgy.status === "ready" ? liturgy.value.seasonCategory : null;
    if (seasonCategory) {
      jobs.push(
        loadShelf(
          setSeasonShelf,
          "season",
          `For ${liturgy.value?.season ?? seasonCategory}`,
          undefined,
          { category: seasonCategory, sort: "popular", limit: 6 },
        ),
      );
    } else {
      setSeasonShelf(null);
    }

    // Use fetchConcurrent to cap simultaneous shelf requests at 4 instead
    // of firing all 5-6 at once. When the backend is slow this prevents the
    // retry interceptor from amplifying 8 initial requests into 24 retries.
    await fetchConcurrent(jobs, 4);
  }, [loadShelf, loadOfflineShelf, liturgy]);

  useEffect(() => {
    if (initialLoading) {
      return;
    }
    // Deferred so the shelf state updates land outside the effect body. The
    // effect re-runs when `liturgy` resolves, which is what fills the season
    // shelf once the calendar has actually named a season.
    void Promise.resolve().then(() => loadAllShelves());
  }, [initialLoading, loadAllShelves]);

  // --- Search / browse results ---------------------------------------------

  const resultsRequestId = useRef(0);

  const runBrowse = useCallback(async () => {
    const token = ++resultsRequestId.current;
    if (!activeCategory && !search.trim()) {
      setSearchResults(null);
      setSearchError(null);
      return;
    }
    setSearchBusy(true);
    const result = await fetchResources({
      category: activeCategory,
      query: search.trim() || null,
      sort,
    });
    // Ignore a response that a newer keystroke has already superseded.
    if (token !== resultsRequestId.current) {
      return;
    }
    setSearchBusy(false);
    if (result.kind === "ok") {
      setSearchResults(result.data);
      setSearchError(null);
    } else {
      setSearchResults([]);
      setSearchError(result.failure.message);
    }
  }, [activeCategory, search, sort]);

  // Debounced so typing does not fire a request per keystroke.
  useEffect(() => {
    if (initialLoading) {
      return;
    }
    const handle = setTimeout(() => void runBrowse(), 300);
    return () => clearTimeout(handle);
  }, [runBrowse, initialLoading]);

  const openCategory = useCallback((category: string | null) => {
    setActiveCategory(category);
  }, []);

  const clearAll = useCallback(() => {
    setActiveCategory(null);
    setSearch("");
    setSort("recent");
  }, []);

  const hasQuery = Boolean(activeCategory) || search.trim().length > 0;
  const gridColumns = isWide ? 4 : width >= 620 ? 3 : 2;

  const browseTitle = useMemo(() => {
    if (search.trim()) {
      return `Results for "${search.trim()}"`;
    }
    return activeCategory ?? "All resources";
  }, [activeCategory, search]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await Promise.all([loadCategories(), loadFavorites(), loadAllShelves()]);
    setRefreshing(false);
  }, [loadAllShelves, loadCategories, loadFavorites]);

  // Authorised contributors only. `require_admin` is enforced server-side on the
  // upload route; this only decides whether to offer the affordance.
  const [canContribute, setCanContribute] = useState(false);
  useEffect(() => {
    void (async () => {
      const stored = await AsyncStorage.multiGet(["user", "user_role"]).catch(() => null);
      if (!stored) {
        setCanContribute(false);
        return;
      }
      const map = Object.fromEntries(stored);
      const role = map.user_role ?? "";
      setCanContribute(role === "admin" || role === "super_admin");
    })();
  }, []);

  const renderShelf = (shelf: Shelf | null) => {
    if (!shelf || shelf.loading) {
      return (
        <View style={styles.shelfLoading}>
          <ActivityIndicator color={ChoirTheme.green} />
          <Text style={styles.shelfLoadingText}>{shelf?.title ?? "Loading"}</Text>
        </View>
      );
    }
    if (shelf.error) {
      return (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>{shelf.title}</Text>
          <ErrorState
            message={shelf.error}
            onRetry={() => void loadAllShelves()}
            retryLabel="Reload"
          />
        </View>
      );
    }
    if (shelf.resources.length === 0) {
      // An empty shelf is stated, not padded. Saying "no choir practice material
      // yet" is honest; showing a skeleton card would not be.
      return (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>{shelf.title}</Text>
          <Text style={styles.shelfEmpty}>
            Nothing published here yet. An authorized contributor can add the first one.
          </Text>
        </View>
      );
    }
    return (
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>{shelf.title}</Text>
        {shelf.subtitle ? <Text style={styles.sectionSubtitle}>{shelf.subtitle}</Text> : null}
        {shelf.resources.map((resource) => (
          <ChoirResourceCard
            key={resource.id}
            resource={resource}
            isFavorited={isFavorited(resource.id)}
            onToggleFavorite={toggleFavorite}
            onPlay={(resource) => void player.play(resource)}
            compact={isWide}
          />
        ))}
      </View>
    );
  };

  if (initialLoading) {
    return (
      <View style={styles.fullBleed}>
        <ScrollView contentContainerStyle={styles.page}>
          <View style={styles.content}>
            <ActivityIndicator size="large" color={ChoirTheme.green} />
            <Text style={styles.loadingText}>Opening the choir library…</Text>
          </View>
        </ScrollView>
      </View>
    );
  }

  return (
    <View style={styles.fullBleed}>
      <ScrollView
        contentContainerStyle={styles.page}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={ChoirTheme.green} />
        }
        keyboardShouldPersistTaps="handled"
      >
        <View style={[styles.content, isWide && styles.contentWide]}>
          {/* --- Hero: compact by design; the library is the page, not the title. --- */}
          <View style={styles.hero}>
            <Text style={styles.heroEyebrow}>Choir Ministry</Text>
            <Text style={styles.heroTitle}>Sacred Music Library</Text>
            <Text style={styles.heroSubtitle}>
              Mass parts, hymnals, psalm settings, scores and rehearsal material for the choir.
            </Text>
            {categories ? (
              <Text style={styles.heroStat}>
                {categories.total} published resource{categories.total === 1 ? "" : "s"}
              </Text>
            ) : null}
          </View>

          {/* --- Today's celebration: entirely server-driven. --- */}
          {liturgy.status === "loading" ? (
            <View style={[styles.liturgyCard, styles.liturgyCardLoading]}>
              <ActivityIndicator color={ChoirTheme.green} />
              <Text style={styles.liturgyLoadingText}>Loading today’s celebration…</Text>
            </View>
          ) : liturgy.status === "ready" && liturgy.value ? (
            <TodayCelebration
              celebration={liturgy.value.celebration}
              rank={liturgy.value.rank}
              season={liturgy.value.season}
              week={liturgy.value.week}
              colour={liturgy.value.colour}
              sundayCycle={liturgy.value.sundayCycle}
              fromCache={liturgy.value.fromCache}
              seasonCategory={liturgy.value.seasonCategory}
              onRetry={liturgy.reload}
            />
          ) : (
            <View style={styles.liturgyCard}>
              <Text style={styles.liturgyTitle}>Today’s celebration unavailable</Text>
              <Text style={styles.liturgyBody}>
                The liturgical calendar could not be reached, so nothing is suggested for today
                rather than a guessed season.
              </Text>
              <Pressable style={styles.retryButton} onPress={liturgy.reload} accessibilityRole="button">
                <Text style={styles.retryText}>Try again</Text>
              </Pressable>
            </View>
          )}

          {/* --- Inline notice: bookmark results and other in-place outcomes --- */}
          {notice ? (
            <View
              style={[
                styles.notice,
                notice.tone === "error" ? styles.noticeError : styles.noticeInfo,
              ]}
              accessibilityLiveRegion="polite"
            >
              <Ionicons
                name={
                  notice.tone === "error"
                    ? "alert-circle-outline"
                    : "information-circle-outline"
                }
                size={16}
                color={notice.tone === "error" ? ChoirTheme.danger : ChoirTheme.green}
              />
              <Text
                style={[
                  styles.noticeText,
                  notice.tone === "error" ? styles.noticeTextError : styles.noticeTextInfo,
                ]}
              >
                {notice.message}
              </Text>
              {notice.tone === "error" && notice.message.startsWith("Sign in") ? (
                <Pressable
                  onPress={() => router.push("/login")}
                  accessibilityRole="button"
                  style={styles.noticeAction}
                >
                  <Text style={styles.noticeActionText}>Sign in</Text>
                </Pressable>
              ) : (
                <Pressable
                  onPress={() => setNotice(null)}
                  hitSlop={10}
                  accessibilityRole="button"
                  accessibilityLabel="Dismiss message"
                  style={styles.noticeDismiss}
                >
                  <Ionicons name="close" size={16} color={ChoirTheme.inkFaint} />
                </Pressable>
              )}
            </View>
          ) : null}

          {/* --- Search --- */}
          <View style={styles.searchWrap}>
            <Ionicons name="search" size={18} color={ChoirTheme.inkFaint} style={styles.searchIcon} />
            <TextInput
              value={search}
              onChangeText={setSearch}
              placeholder="Search songs, composers, texts…"
              placeholderTextColor={ChoirTheme.inkFaint}
              style={styles.searchInput}
              accessibilityLabel="Search the choir library"
              returnKeyType="search"
              autoCorrect={false}
            />
            {search.length > 0 ? (
              <Pressable
                onPress={() => setSearch("")}
                hitSlop={12}
                accessibilityRole="button"
                accessibilityLabel="Clear search"
                style={styles.searchClear}
              >
                <Ionicons name="close-circle" size={18} color={ChoirTheme.inkFaint} />
              </Pressable>
            ) : null}
          </View>

          {hasQuery ? (
            /* --- Focused browse results replace the shelves --- */
            <View style={styles.section}>
              <View style={styles.browseHeader}>
                <Text style={styles.sectionTitle}>{browseTitle}</Text>
                <View style={styles.browseActions}>
                  <SortToggle value={sort} onChange={setSort} />
                  <Pressable
                    onPress={clearAll}
                    hitSlop={8}
                    accessibilityRole="button"
                    accessibilityLabel="Clear all filters"
                  >
                    <Text style={styles.clearLink}>Clear</Text>
                  </Pressable>
                </View>
              </View>

              {searchBusy ? (
                <View style={styles.shelfLoading}>
                  <ActivityIndicator color={ChoirTheme.green} />
                </View>
              ) : searchError ? (
                <ErrorState
                  message={searchError}
                  onRetry={() => void runBrowse()}
                />
              ) : searchResults && searchResults.length === 0 ? (
                <View style={styles.emptyBox}>
                  <Ionicons name="search-outline" size={34} color={ChoirTheme.inkFaint} />
                  <Text style={styles.emptyTitle}>No resources match</Text>
                  <Text style={styles.emptyBody}>
                    Nothing published matches these filters. Try a different category, or clear
                    the search.
                  </Text>
                </View>
              ) : (
                searchResults?.map((resource) => (
                  <ChoirResourceCard
                    key={resource.id}
                    resource={resource}
                    isFavorited={isFavorited(resource.id)}
                    onToggleFavorite={toggleFavorite}
                    onPlay={(resource) => void player.play(resource)}
                    compact={isWide}
                  />
                ))
              )}
            </View>
          ) : (
            <>
              {/* --- The 27 categories, grouped and counted --- */}
              {categoriesError ? (
                <ErrorState message={categoriesError} onRetry={() => void loadCategories()} />
              ) : categories ? (
                <View>
                  {categoriesOffline ? (
                    /* Say so, rather than showing stale counts as if they were live. */
                    <View style={styles.offlineBanner} accessibilityLiveRegion="polite">
                      <Ionicons name="cloud-offline-outline" size={16} color={ChoirTheme.inkMuted} />
                      <Text style={styles.offlineBannerText}>
                        Offline — showing the categories saved on this device. Counts may be out of date.
                      </Text>
                    </View>
                  ) : null}
                  {categories.sections.map((section) => (
                  <View key={section.title} style={styles.section}>
                    <View style={styles.sectionHead}>
                      <Ionicons
                        name={SECTION_ICON[section.title] ?? "folder-open"}
                        size={18}
                        color={ChoirTheme.gold}
                      />
                      <Text style={styles.sectionTitle}>{section.title}</Text>
                    </View>
                    <View style={[styles.categoryGrid, { gap: ChoirSpace.sm }]}>
                      {section.categories.map((category) => {
                        const count = categories.counts[category] ?? 0;
                        return (
                          <Pressable
                            key={category}
                            onPress={() => openCategory(category)}
                            accessibilityRole="button"
                            accessibilityLabel={`${category}, ${count} resource${
                              count === 1 ? "" : "s"
                            }`}
                            style={({ pressed }) => [
                              styles.categoryTile,
                              // Tiles are laid out in a fixed column count so the
                              // rows line up instead of stretching a flex-wrap row.
                              { width: `${100 / gridColumns}%` },
                              count === 0 && styles.categoryTileEmpty,
                              pressed && styles.categoryTilePressed,
                            ]}
                          >
                            <View style={styles.categoryTileInner}>
                              <Ionicons
                                name={iconForCategory(category)}
                                size={20}
                                color={count === 0 ? ChoirTheme.inkFaint : ChoirTheme.green}
                              />
                              <Text
                                style={[
                                  styles.categoryTileLabel,
                                  count === 0 && styles.categoryTileLabelEmpty,
                                ]}
                                numberOfLines={2}
                              >
                                {category}
                              </Text>
                              <Text style={styles.categoryTileCount}>
                                {count} resource{count === 1 ? "" : "s"}
                              </Text>
                            </View>
                          </Pressable>
                        );
                      })}
                    </View>
                  </View>
                  ))}
                </View>
              ) : null}

              {/* --- Shelves --- */}
              {offlineShelf ? renderShelf(offlineShelf) : null}
              {seasonShelf ? renderShelf(seasonShelf) : null}
              {renderShelf(massShelf)}
              {renderShelf(featuredShelf)}
              {renderShelf(practiceShelf)}
              {renderShelf(recentShelf)}

              {/* --- Contributor action, only when authorised --- */}
              {canContribute ? (
                <Pressable
                  onPress={() => router.push("/admin/upload")}
                  accessibilityRole="button"
                  style={styles.contribute}
                >
                  <Ionicons name="cloud-upload-outline" size={22} color={ChoirTheme.white} />
                  <View style={styles.contributeText}>
                    <Text style={styles.contributeTitle}>Add a choir resource</Text>
                    <Text style={styles.contributeBody}>
                      Upload a score, recording or lyric sheet for review.
                    </Text>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color={ChoirTheme.white} />
                </Pressable>
              ) : null}
            </>
          )}

          <View style={styles.footer}>
            <Text style={styles.footerText}>
              Music and texts remain the property of their authors and publishers.
            </Text>
          </View>
        </View>
      </ScrollView>
    </View>
  );
}

/** Today's celebration, with the accent taken from the real liturgical colour. */
function TodayCelebration({
  celebration,
  rank,
  season,
  week,
  colour,
  sundayCycle,
  fromCache,
  seasonCategory,
  onRetry,
}: {
  celebration: string | null;
  rank: string | null;
  season: string | null;
  week: number | null;
  colour: string | null;
  sundayCycle: string | null;
  fromCache: boolean;
  seasonCategory: string | null;
  onRetry: () => void;
}) {
  const accent = liturgicalAccent(colour);
  const parts = [
    season,
    week != null ? `Week ${week}` : null,
    sundayCycle ? `Cycle ${sundayCycle}` : null,
  ].filter((part): part is string => Boolean(part));

  return (
    <View
      style={[styles.liturgyCard, { borderLeftColor: accent.accent, backgroundColor: accent.tint }]}
    >
      <View style={styles.liturgyHeader}>
        <Ionicons name="sunny-outline" size={18} color={accent.accent} />
        <Text style={styles.liturgyEyebrow}>Today’s Celebration</Text>
        {fromCache ? (
          <View style={styles.offlinePill}>
            <Text style={styles.offlinePillText}>Offline</Text>
          </View>
        ) : null}
      </View>

      <Text style={styles.liturgyTitle}>{celebration ?? "Ordinary Time"}</Text>

      {parts.length > 0 ? (
        <View style={styles.liturgyMetaRow}>
          {parts.map((part) => (
            <View key={part} style={[styles.liturgyPill, { borderColor: accent.accent }]}>
              <Text style={[styles.liturgyPillText, { color: accent.accent }]}>{part}</Text>
            </View>
          ))}
        </View>
      ) : null}

      <Text style={styles.liturgyBody}>
        {seasonCategory
          ? `The library carries ${seasonCategory} material for this season.`
          : "Choose a category below to prepare music for this celebration."}
      </Text>

      {rank ? <Text style={styles.liturgyRank}>Rank: {rank}</Text> : null}
    </View>
  );
}

function SortToggle({
  value,
  onChange,
}: {
  value: ChoirSort;
  onChange: (sort: ChoirSort) => void;
}) {
  const options: { value: ChoirSort; label: string }[] = [
    { value: "recent", label: "Newest" },
    { value: "popular", label: "Most loved" },
    { value: "title", label: "A–Z" },
  ];
  return (
    <View style={styles.sortGroup} accessibilityRole="radiogroup">
      {options.map((option) => {
        const selected = value === option.value;
        return (
          <Pressable
            key={option.value}
            onPress={() => onChange(option.value)}
            accessibilityRole="radio"
            accessibilityState={{ selected }}
            style={[styles.sortOption, selected && styles.sortOptionActive]}
          >
            <Text style={[styles.sortOptionText, selected && styles.sortOptionTextActive]}>
              {option.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  fullBleed: {
    flex: 1,
    backgroundColor: ChoirTheme.canvas,
  },
  page: {
    paddingBottom: ChoirSpace.xxl * 2,
  },
  content: {
    paddingHorizontal: ChoirSpace.lg,
    paddingTop: ChoirSpace.lg,
    alignSelf: "center",
    width: "100%",
  },
  contentWide: {
    maxWidth: MaxChoirContentWidth,
  },

  hero: {
    marginBottom: ChoirSpace.lg,
  },
  heroEyebrow: {
    fontSize: ChoirType.micro,
    letterSpacing: 1.2,
    textTransform: "uppercase",
    color: ChoirTheme.gold,
    fontWeight: "700",
  },
  heroTitle: {
    fontSize: ChoirType.hero,
    fontWeight: "800",
    color: ChoirTheme.greenDark,
    marginTop: ChoirSpace.xs,
  },
  heroSubtitle: {
    fontSize: ChoirType.body,
    color: ChoirTheme.inkMuted,
    marginTop: ChoirSpace.sm,
    lineHeight: 22,
    maxWidth: 620,
  },
  heroStat: {
    fontSize: ChoirType.meta,
    color: ChoirTheme.inkFaint,
    marginTop: ChoirSpace.sm,
    fontWeight: "600",
  },

  liturgyCard: {
    borderRadius: ChoirRadius.md,
    borderLeftWidth: 4,
    borderWidth: 1,
    borderColor: ChoirTheme.border,
    padding: ChoirSpace.lg,
    marginBottom: ChoirSpace.lg,
    backgroundColor: ChoirTheme.surface,
  },
  liturgyCardLoading: {
    flexDirection: "row",
    alignItems: "center",
    gap: ChoirSpace.md,
    borderLeftColor: ChoirTheme.green,
  },
  liturgyLoadingText: {
    color: ChoirTheme.inkMuted,
    fontSize: ChoirType.meta,
  },
  liturgyHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: ChoirSpace.sm,
  },
  liturgyEyebrow: {
    fontSize: ChoirType.micro,
    letterSpacing: 1,
    textTransform: "uppercase",
    fontWeight: "700",
    color: ChoirTheme.inkMuted,
    flex: 1,
  },
  offlinePill: {
    backgroundColor: ChoirTheme.goldTint,
    borderRadius: ChoirRadius.pill,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  offlinePillText: {
    fontSize: ChoirType.micro,
    fontWeight: "700",
    color: ChoirTheme.gold,
  },
  liturgyTitle: {
    fontSize: ChoirType.section,
    fontWeight: "700",
    color: ChoirTheme.ink,
    marginTop: ChoirSpace.sm,
  },
  liturgyMetaRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: ChoirSpace.xs,
    marginTop: ChoirSpace.md,
  },
  liturgyPill: {
    borderWidth: 1,
    borderRadius: ChoirRadius.pill,
    paddingHorizontal: 10,
    paddingVertical: 3,
  },
  liturgyPillText: {
    fontSize: ChoirType.micro,
    fontWeight: "700",
  },
  liturgyBody: {
    fontSize: ChoirType.meta,
    color: ChoirTheme.inkMuted,
    marginTop: ChoirSpace.md,
    lineHeight: 20,
  },
  liturgyRank: {
    fontSize: ChoirType.micro,
    color: ChoirTheme.inkFaint,
    marginTop: ChoirSpace.sm,
  },
  retryButton: {
    marginTop: ChoirSpace.md,
    alignSelf: "flex-start",
    backgroundColor: ChoirTheme.green,
    paddingHorizontal: ChoirSpace.lg,
    paddingVertical: ChoirSpace.sm,
    borderRadius: ChoirRadius.sm,
    minHeight: MinTouchTarget,
    justifyContent: "center",
  },
  retryText: {
    color: ChoirTheme.white,
    fontWeight: "700",
    fontSize: ChoirType.meta,
  },

  notice: {
    flexDirection: "row",
    alignItems: "center",
    gap: ChoirSpace.sm,
    borderRadius: ChoirRadius.sm,
    borderWidth: 1,
    padding: ChoirSpace.md,
    marginBottom: ChoirSpace.lg,
  },
  noticeInfo: {
    backgroundColor: ChoirTheme.greenTint,
    borderColor: "#BEDCC7",
  },
  noticeError: {
    backgroundColor: ChoirTheme.dangerTint,
    borderColor: "#F3C2BD",
  },
  noticeText: {
    flex: 1,
    fontSize: ChoirType.meta,
    lineHeight: 19,
  },
  noticeTextInfo: {
    color: ChoirTheme.greenDark,
  },
  noticeTextError: {
    color: ChoirTheme.danger,
  },
  noticeAction: {
    minHeight: MinTouchTarget,
    minWidth: MinTouchTarget,
    alignItems: "center",
    justifyContent: "center",
  },
  noticeActionText: {
    color: ChoirTheme.danger,
    fontWeight: "700",
    fontSize: ChoirType.meta,
  },
  noticeDismiss: {
    minHeight: MinTouchTarget,
    minWidth: MinTouchTarget,
    alignItems: "center",
    justifyContent: "center",
  },

  searchWrap: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: ChoirTheme.surface,
    borderRadius: ChoirRadius.pill,
    borderWidth: 1,
    borderColor: ChoirTheme.border,
    paddingHorizontal: ChoirSpace.lg,
    minHeight: MinTouchTarget + 6,
    marginBottom: ChoirSpace.xl,
    ...ChoirShadow,
  },
  searchIcon: {
    marginRight: ChoirSpace.sm,
  },
  searchInput: {
    flex: 1,
    fontSize: ChoirType.body,
    color: ChoirTheme.ink,
    paddingVertical: ChoirSpace.md,
  },
  searchClear: {
    padding: ChoirSpace.xs,
  },

  section: {
    marginBottom: ChoirSpace.xxl,
  },
  sectionHead: {
    flexDirection: "row",
    alignItems: "center",
    gap: ChoirSpace.sm,
    marginBottom: ChoirSpace.sm,
  },
  offlineBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: ChoirSpace.sm,
    padding: ChoirSpace.md,
    marginBottom: ChoirSpace.lg,
    borderRadius: ChoirRadius.sm,
    backgroundColor: ChoirTheme.surfaceMuted,
    borderWidth: 1,
    borderColor: ChoirTheme.border,
  },
  offlineBannerText: {
    flex: 1,
    fontSize: ChoirType.micro,
    color: ChoirTheme.inkMuted,
    lineHeight: 17,
  },

  sectionTitle: {
    fontSize: ChoirType.section,
    fontWeight: "700",
    color: ChoirTheme.greenDark,
  },
  sectionSubtitle: {
    fontSize: ChoirType.meta,
    color: ChoirTheme.inkFaint,
    marginTop: 2,
    marginBottom: ChoirSpace.md,
  },

  browseHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    flexWrap: "wrap",
    gap: ChoirSpace.sm,
    marginBottom: ChoirSpace.md,
  },
  browseActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: ChoirSpace.md,
  },
  clearLink: {
    color: ChoirTheme.danger,
    fontWeight: "700",
    fontSize: ChoirType.meta,
  },
  sortGroup: {
    flexDirection: "row",
    backgroundColor: ChoirTheme.surfaceMuted,
    borderRadius: ChoirRadius.pill,
    padding: 3,
    gap: 2,
  },
  sortOption: {
    paddingHorizontal: ChoirSpace.md,
    paddingVertical: 6,
    borderRadius: ChoirRadius.pill,
    minHeight: 34,
    justifyContent: "center",
  },
  sortOptionActive: {
    backgroundColor: ChoirTheme.surface,
  },
  sortOptionText: {
    fontSize: ChoirType.micro,
    fontWeight: "700",
    color: ChoirTheme.inkMuted,
  },
  sortOptionTextActive: {
    color: ChoirTheme.green,
  },

  categoryGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
  },
  categoryTile: {
    padding: ChoirSpace.xs,
  },
  categoryTileInner: {
    backgroundColor: ChoirTheme.surface,
    borderRadius: ChoirRadius.md,
    borderWidth: 1,
    borderColor: ChoirTheme.border,
    paddingVertical: ChoirSpace.lg,
    paddingHorizontal: ChoirSpace.md,
    minHeight: 118,
    justifyContent: "center",
    alignItems: "center",
    gap: ChoirSpace.xs,
    ...ChoirShadow,
  },
  categoryTileEmpty: {
    backgroundColor: ChoirTheme.surfaceMuted,
    borderStyle: "dashed",
    borderColor: ChoirTheme.borderStrong,
    elevation: 0,
    shadowOpacity: 0,
  },
  categoryTilePressed: {
    opacity: 0.8,
  },
  categoryTileLabel: {
    fontSize: ChoirType.meta,
    fontWeight: "700",
    color: ChoirTheme.ink,
    textAlign: "center",
  },
  categoryTileLabelEmpty: {
    color: ChoirTheme.inkMuted,
  },
  categoryTileCount: {
    fontSize: ChoirType.micro,
    color: ChoirTheme.inkFaint,
  },

  shelfLoading: {
    flexDirection: "row",
    alignItems: "center",
    gap: ChoirSpace.md,
    paddingVertical: ChoirSpace.lg,
  },
  shelfLoadingText: {
    color: ChoirTheme.inkMuted,
    fontSize: ChoirType.meta,
  },
  shelfEmpty: {
    color: ChoirTheme.inkMuted,
    fontSize: ChoirType.meta,
    lineHeight: 20,
    backgroundColor: ChoirTheme.surfaceMuted,
    borderRadius: ChoirRadius.sm,
    padding: ChoirSpace.lg,
  },

  emptyBox: {
    alignItems: "center",
    paddingVertical: ChoirSpace.xxl * 1.5,
    paddingHorizontal: ChoirSpace.lg,
    gap: ChoirSpace.sm,
  },
  emptyTitle: {
    fontSize: ChoirType.cardTitle,
    fontWeight: "700",
    color: ChoirTheme.ink,
  },
  emptyBody: {
    fontSize: ChoirType.meta,
    color: ChoirTheme.inkMuted,
    textAlign: "center",
    lineHeight: 20,
  },

  loadingText: {
    marginTop: ChoirSpace.md,
    color: ChoirTheme.inkMuted,
    fontSize: ChoirType.meta,
  },

  contribute: {
    flexDirection: "row",
    alignItems: "center",
    gap: ChoirSpace.md,
    backgroundColor: ChoirTheme.green,
    borderRadius: ChoirRadius.md,
    padding: ChoirSpace.lg,
    marginBottom: ChoirSpace.xxl,
    minHeight: MinTouchTarget + 20,
  },
  contributeText: {
    flex: 1,
  },
  contributeTitle: {
    color: ChoirTheme.white,
    fontWeight: "700",
    fontSize: ChoirType.body,
  },
  contributeBody: {
    color: "#D8EBDD",
    fontSize: ChoirType.micro,
    marginTop: 2,
  },

  footer: {
    borderTopWidth: 1,
    borderTopColor: ChoirTheme.border,
    paddingTop: ChoirSpace.lg,
  },
  footerText: {
    fontSize: ChoirType.micro,
    color: ChoirTheme.inkFaint,
    lineHeight: 18,
  },
});