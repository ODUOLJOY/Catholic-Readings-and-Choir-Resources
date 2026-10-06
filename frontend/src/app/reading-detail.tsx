/**
 * The Catholic digital missal: the Reading screen.
 *
 * Design goals (see project directive):
 * - calm, prayerful, clean, highly readable, mobile-friendly, accessible
 * - the Scripture text is the visual priority (serif body, 820px max width)
 * - NOT a news feed / NOT "every piece of information in colourful cards"
 * - works offline (cache-first via `readingsService`), with EN/Kiswahili
 *   switch, date navigation (prev/today/next + calendar picker), bookmarks,
 *   and the liturgical header supplied authoritatively by the backend
 *
 * No Scripture or liturgical metadata is hardcoded: every label, colour,
 * colour name, season, week, cycle and verse comes from the typed
 * `readingsService` façade, which only ever returns what the
 * `/api/readings/{date}` and `/api/v1/liturgy/date/{date}` endpoints provide.
 */
import { useEffect, useRef, useState } from "react";
import {
  Alert,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons, MaterialCommunityIcons } from "@expo/vector-icons";

import { MaxContentWidth, Spacing, Fonts } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import {
  MissalLoadResult,
  ReadingLanguage,
  ReadingSection,
  getLanguage,
  getMissalByDate,
  getReadingById,
  refreshMissal,
  setLanguage,
} from "@/services/readingsService";
import { favoriteService } from "@/services/favoriteService";
import { classifyRequestFailure, RequestFailure } from "@/lib/requestFailure";
import { ErrorState, LoadingState } from "@/components/ScreenStates";
import { CalendarPicker } from "@/components/CalendarPicker";
import {
  kenyaDateString,
  shiftCalendarDate,
} from "@/utils/calendar";

const BRAND = "#0B6623";
const LITURGICAL_COLOR_HEX: Record<string, string> = {
  Green: "#16a34a",
  White: "#cbd5e1",
  Red: "#b91c1c",
  Purple: "#6b21a8",
  Violet: "#6b21a8",
  Rose: "#d97706",
  Black: "#1f2937",
};

const GENERIC_CELEBRATIONS = new Set(["Weekday", "Feria", "Ferias", "Sunday"]);

type ThemeColors = ReturnType<typeof useTheme>;

function liturgicalColorHex(color: string | null | undefined): string {
  if (!color) return BRAND;
  return LITURGICAL_COLOR_HEX[color] ?? BRAND;
}

// A date in "yyyy-mm-dd" rendered at Nairobi noon so the UTC day is stable.
function parseDateStr(dateStr: string): Date {
  const [y, m, d] = dateStr.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d, 12));
}

function localeFor(language: ReadingLanguage): string {
  return language === "Kiswahili" ? "sw-KE" : "en-GB";
}

function weekdayLong(dateStr: string, language: ReadingLanguage): string {
  return new Intl.DateTimeFormat(localeFor(language), {
    timeZone: "Africa/Nairobi",
    weekday: "long",
  }).format(parseDateStr(dateStr));
}

function formatDateLong(dateStr: string, language: ReadingLanguage): string {
  return new Intl.DateTimeFormat(localeFor(language), {
    timeZone: "Africa/Nairobi",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(parseDateStr(dateStr));
}

function ordinal(n: number): string {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return `${n}${s[(v - 20) % 10] || s[v] || s[0]}`;
}

function capitalize(s: string | null | undefined): string {
  if (!s) return "";
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function rankBadgeColor(rank: string): string {
  const r = rank.toLowerCase();
  if (r.includes("solemn")) return "#b4933b"; // gold
  if (r.includes("memorial") && r.includes("opt")) return "#2563eb"; // blue
  if (r.includes("memorial")) return "#d97706"; // orange
  if (r.includes("feast")) return "#b91c1c"; // red
  return BRAND;
}

export default function ReadingDetailScreen() {
  const { date: dateParam, id: idParam } = useLocalSearchParams<{
    date?: string;
    id?: string;
  }>();
  const router = useRouter();
  const theme = useTheme();

  // The date shown. Resolved from the id param (search links by id) or from
  // "today" so we always request a concrete date string from the backend.
  const [selectedDate, setSelectedDate] = useState<string | null>(
    dateParam ?? null,
  );
  const [language, setLanguageState] = useState<ReadingLanguage>("English");
  const [missal, setMissal] = useState<MissalLoadResult | null>(null);
  const [status, setStatus] = useState<"loading" | "error" | "empty" | "ready">(
    "loading",
  );
  const [error, setError] = useState<RequestFailure | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [showCalendar, setShowCalendar] = useState(false);
  const [bookmarked, setBookmarked] = useState<boolean | null>(null);

  // Monotonic token so a slow response can never overwrite a newer one.
  const activeTokenRef = useRef(0);

  useEffect(() => {
    void getLanguage().then((lang) => setLanguageState(lang));
  }, []);

  // Resolve the date on first render from the id param, else default to today.
  useEffect(() => {
    if (selectedDate) return;

    if (idParam) {
      let active = true;
      getReadingById(Number(idParam), language)
        .then((reading) => {
          if (!active) return;
          setSelectedDate(reading.reading_date);
        })
        .catch((e: unknown) => {
          if (!active) return;
          setError(
            classifyRequestFailure(e, {
              fallbackNotFound: "Reading not found.",
              fallbackMessage:
                "Could not load the readings. Check your connection and try again.",
            }),
          );
          setStatus("error");
        });
      return () => {
        active = false;
      };
    }

    const today = kenyaDateString(new Date());
    void Promise.resolve().then(() => {
      setSelectedDate(today);
      router.setParams({ date: today } as any);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idParam]);

  async function load(dateStr: string) {
    const token = ++activeTokenRef.current;
    setStatus("loading");
    setError(null);
    try {
      const result = await getMissalByDate(dateStr, language);
      if (activeTokenRef.current !== token) return; // superseded
      setMissal(result);
      setStatus(result.notFound ? "ready" : result.data.sections.length ? "ready" : "empty");
      if (dateParam !== dateStr) {
        router.setParams({ date: dateStr } as any);
      }
    } catch (e) {
      if (activeTokenRef.current !== token) return;
      setError(
        classifyRequestFailure(e, {
          fallbackNotFound: "There is no reading for this date.",
          fallbackMessage:
            "Could not load the readings. Check your connection and try again.",
        }),
      );
      setStatus("error");
    }
  }

  useEffect(() => {
    if (selectedDate) {
      void Promise.resolve().then(() => load(selectedDate));
    }
  }, [selectedDate, language]);

  // Bookmark state, keyed off the resolved reading id.
  useEffect(() => {
    const readingId = missal?.data.id ?? null;
    if (readingId == null) {
      void Promise.resolve().then(() => setBookmarked(null));
      return;
    }
    let active = true;
    void favoriteService
      .getFavoritesOptional()
      .then((favs) => {
        if (!active) return;
        setBookmarked(
          favs.some(
            (f) =>
              f.resource_type === "reading" &&
              f.target_resource_id === readingId,
          ),
        );
      })
      .catch(() => {
        if (!active) return;
        setBookmarked(null);
      });
    return () => {
      active = false;
    };
  }, [missal?.data.id]);

  async function refresh() {
    if (!selectedDate) return;
    setRefreshing(true);
    try {
      const result = await refreshMissal(selectedDate, language);
      setMissal(result);
      setStatus(result.notFound ? "ready" : result.data.sections.length ? "ready" : "empty");
      setError(null);
    } catch (e) {
      setError(
        classifyRequestFailure(e, {
          fallbackNotFound: "There is no reading for this date.",
          fallbackMessage:
            "Could not refresh the readings. Check your connection and try again.",
        }),
      );
      setStatus("error");
    } finally {
      setRefreshing(false);
    }
  }

  function navigateDate(days: number) {
    if (!selectedDate) return;
    setSelectedDate(shiftCalendarDate(selectedDate, days));
  }

  function goToToday() {
    setSelectedDate(kenyaDateString(new Date()));
  }

  function pickDate(date: Date) {
    setShowCalendar(false);
    setSelectedDate(kenyaDateString(date));
  }

  function toggleLanguage() {
    const next: ReadingLanguage =
      language === "English" ? "Kiswahili" : "English";
    void setLanguage(next);
    setLanguageState(next);
  }

  async function toggleBookmark() {
    const readingId = missal?.data.id;
    if (!readingId) return;
    try {
      if (bookmarked) {
        const favs = await favoriteService.getFavoritesOptional();
        const match = favs.find(
          (f) =>
            f.resource_type === "reading" &&
            f.target_resource_id === readingId,
        );
        if (match) await favoriteService.deleteFavorite(match.id);
        setBookmarked(false);
      } else {
        await favoriteService.createFavorite("reading", readingId);
        setBookmarked(true);
      }
    } catch (e) {
      const code = (e as { response?: { status?: number } })?.response?.status;
      if (code === 401) {
        Alert.alert(
          "Sign in to bookmark",
          "Save this reading to your bookmarks by signing in.",
          [
            { text: "Cancel", style: "cancel" },
            {
              text: "Sign in",
              onPress: () => router.push("/login" as any),
            },
          ],
        );
        return;
      }
      Alert.alert("Could not update bookmark", "Please try again.");
    }
  }

  // --- Derived header fields (authoritative backend values) ---
  const header = missal?.data.header;
  const reading = missal?.data;

  const weekday = selectedDate ? weekdayLong(selectedDate, language) : "";
  const colorHex = liturgicalColorHex(header?.liturgicalColor);
  const seasonLine = header?.season ?? "";

  const weekLine =
    header?.season === "Ordinary Time" && header?.week
      ? `${ordinal(header.week)} Week in Ordinary Time`
      : "";

  const weekdayOfWeekLine =
    header?.season === "Ordinary Time" && header?.week
      ? `${weekday} of the ${ordinal(header.week)} Week in Ordinary Time`
      : "";

  const cyclesLine =
    (header?.weekdayCycle ? `Cycle ${header.weekdayCycle}` : "") +
    (header?.sundayCycle
      ? ` · Year ${header.sundayCycle}`
      : "");

  const sections = missal?.data.sections ?? [];
  const empty = !missal?.notFound && sections.length === 0;

  const notFoundMessage = !missal?.notFound
    ? ""
    : language === "Kiswahili"
      ? missal.englishFallback
        ? "Kiswahili text is not available for this reading yet. English text is shown below where it exists."
        : "Kiswahili text is not available for this reading yet."
      : "The full reading text for this date is not yet available.";

  const loadingInitially = status === "loading" && !missal;
  const hardError = status === "error" && !missal && !!error;
  const softError = status === "error" && !!missal && !!error;

  if (loadingInitially) {
    return (
      <View style={[styles.root, { backgroundColor: theme.background }]}>
        <LoadingState label="Loading today's readings…" />
      </View>
    );
  }

  if (hardError) {
    return (
      <View style={[styles.root, { backgroundColor: theme.background }]}>
        <ErrorState
          message={error!.message}
          retryLabel="Try again"
          onRetry={() => {
            if (selectedDate) void load(selectedDate);
          }}
        />
      </View>
    );
  }

  return (
    <View style={[styles.root, { backgroundColor: theme.background }]}>
      <ScrollView
        contentContainerStyle={[styles.scroll, { backgroundColor: theme.background }]}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={refresh}
            colors={[BRAND]}
            tintColor={BRAND}
          />
        }
        showsVerticalScrollIndicator={false}
      >
        {/* TOP APP BAR */}
        <View style={styles.appBar}>
          <TouchableOpacity
            accessibilityRole="button"
            accessibilityLabel="Go back"
            onPress={() => {
              if (router.canGoBack()) router.back();
              else router.replace("/(tabs)/index" as any);
            }}
            style={styles.backButton}
          >
            <Ionicons name="arrow-back" size={24} color={theme.text} />
          </TouchableOpacity>

          <Text
            style={[styles.appBarTitle, { color: theme.text }]}
            accessibilityRole="header"
          >
            Readings
          </Text>

          <View style={styles.appBarRight}>
            {reading?.id != null && (
              <TouchableOpacity
                accessibilityRole="button"
                accessibilityLabel={
                  bookmarked ? "Remove from bookmarks" : "Add to bookmarks"
                }
                accessibilityHint="Bookmark this reading"
                onPress={() => void toggleBookmark()}
                style={styles.bookmarkButton}
              >
                <Ionicons
                  name={bookmarked ? "bookmark" : "bookmark-outline"}
                  size={22}
                  color={bookmarked ? "#F59E0B" : theme.textSecondary}
                />
              </TouchableOpacity>
            )}
            <TouchableOpacity
              accessibilityRole="button"
              accessibilityLabel="Switch language"
              onPress={toggleLanguage}
              style={[
                styles.languageButton,
                { backgroundColor: theme.backgroundElement },
              ]}
            >
              <Text
                style={[
                  styles.languageText,
                  language === "English" && styles.languageTextActive,
                ]}
              >
                EN
              </Text>
              <Text style={styles.languageDot}>|</Text>
              <Text
                style={[
                  styles.languageText,
                  language === "Kiswahili" && styles.languageTextActive,
                ]}
              >
                Sw
              </Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Soft (offline) error banner: refresh failed, cached copy still shown. */}
        {softError ? (
          <View
            style={[styles.errorBanner, { backgroundColor: "#FDECEA" }]}
          >
            <Ionicons name="alert-circle" size={14} color="#b91c1c" />
            <Text
              style={[styles.fallbackText, { color: theme.textSecondary }]}
            >
              {error!.message} · Pull again to retry.
            </Text>
          </View>
        ) : null}

        {/* NOT FOUND / LANGUAGE UNAVAILABLE NOTICE */}
        {missal?.notFound ? (
          <View style={[styles.fallbackBanner, { backgroundColor: "#EFF6FF" }]}>
            <Ionicons name="information-circle" size={16} color="#3b82f6" />
            <Text style={[styles.fallbackText, { color: theme.textSecondary }]}>
              {notFoundMessage}
            </Text>
          </View>
        ) : null}

        {/* DATE / LITURGICAL HEADER */}
        {header && selectedDate ? (
          <View style={styles.headerCard}>
            <Text style={styles.weekday}>{weekday}</Text>
            <Text
              style={[styles.date, { color: theme.textSecondary }]}
            >
              {formatDateLong(selectedDate, language)}
            </Text>

            {header.celebration &&
            !GENERIC_CELEBRATIONS.has(header.celebration) ? (
              <View style={styles.celebrationRow}>
                <Text style={[styles.celebration, { color: theme.text }]}>
                  {header.celebration}
                </Text>
                {header.rank ? (
                  <View
                    style={[
                      styles.rankBadge,
                      { backgroundColor: rankBadgeColor(header.rank) },
                    ]}
                  >
                    <Text style={styles.rankText}>{header.rank}</Text>
                  </View>
                ) : null}
              </View>
            ) : null}

            <View style={styles.colorRow}>
              <View
                style={[styles.colorDot, { backgroundColor: colorHex }]}
              />
              <Text
                style={[styles.colorLine, { color: theme.textSecondary }]}
              >
                {capitalize(header.liturgicalColor)}
                {seasonLine ? ` • ${seasonLine}` : ""}
              </Text>
            </View>

            {weekLine ? (
              <Text style={[styles.weekLine, { color: theme.text }]}>
                {weekLine}
              </Text>
            ) : null}

            {weekdayOfWeekLine ? (
              <Text
                style={[styles.weekdayOfWeek, { color: theme.textSecondary }]}
              >
                {weekdayOfWeekLine}
              </Text>
            ) : null}

            {cyclesLine ? (
              <Text style={[styles.cycleLine, { color: theme.textSecondary }]}>
                {cyclesLine}
              </Text>
            ) : null}

            {header.verificationStatus &&
            header.verificationStatus !== "verified" ? (
              <Text style={styles.unverified}>Unverified</Text>
            ) : null}
          </View>
        ) : null}

        {/* READING SUMMARY */}
        {!empty && sections.length > 1 ? (
          <View
            style={[
              styles.summaryCard,
              {
                backgroundColor: theme.backgroundElement,
                borderColor: "#E5EAE6",
              },
            ]}
          >
            <Text
              style={[styles.summaryTitle, { color: theme.textSecondary }]}
            >
              Today&apos;s Readings
            </Text>
            {sections.map((s) => (
              <View key={s.type} style={styles.summaryRow}>
                <Text
                  style={[styles.summaryLabel, { color: theme.textSecondary }]}
                >
                  {s.title}
                </Text>
                <Text style={[styles.summaryRef, { color: theme.text }]}>
                  {s.reference || ""}
                </Text>
              </View>
            ))}
          </View>
        ) : null}

        {/* READING CONTENT */}
        {empty ? (
          <View style={styles.emptyCard}>
            <Ionicons
              name="book-outline"
              size={36}
              color={theme.textSecondary}
            />
            <Text
              style={[styles.emptyText, { color: theme.textSecondary }]}
            >
              No reading is available for this date.
            </Text>
          </View>
        ) : (
          sections.map((section) => renderSection(section, theme))
        )}

        {/* English fallback body (read-only), rendered when Swahili was requested */}
        {missal?.notFound &&
        language === "Kiswahili" &&
        missal.englishFallback &&
        missal.englishFallback.sections.length > 0 ? (
          <View style={styles.fallbackBlock}>
            <Text
              style={[
                styles.fallbackBlockTitle,
                { color: theme.textSecondary },
              ]}
            >
              English readings
            </Text>
            {missal.englishFallback.sections.map((s) =>
              renderSection(s, theme, true),
            )}
          </View>
        ) : null}

        {reading?.reflection ? (
          <View
            style={[
              styles.reflectionCard,
              {
                backgroundColor: theme.backgroundElement,
                borderColor: "#E5EAE6",
              },
            ]}
          >
            <Text
              style={[styles.reflection, { color: theme.textSecondary }]}
            >
              {reading.reflection}
            </Text>
          </View>
        ) : null}

        {reading?.prayer ? (
          <View style={styles.prayerCard}>
            <Text style={[styles.prayer, { color: theme.text }]}>
              {reading.prayer}
            </Text>
          </View>
        ) : null}
      </ScrollView>

      {/* BOTTOM ACTIONS (pinned) */}
      <View
        style={[
          styles.bottomBar,
          {
            backgroundColor: theme.background,
            borderTopColor: theme.backgroundElement,
          },
        ]}
      >
        <TouchableOpacity
          accessibilityRole="button"
          accessibilityLabel="Previous day"
          onPress={() => navigateDate(-1)}
          style={styles.bottomButton}
        >
          <Ionicons name="chevron-back" size={22} color={BRAND} />
          <Text style={styles.bottomButtonText}>Yesterday</Text>
        </TouchableOpacity>

        <TouchableOpacity
          accessibilityRole="button"
          accessibilityLabel="Today"
          onPress={goToToday}
          style={[styles.bottomButton, styles.bottomButtonAccent]}
        >
          <Text style={styles.bottomButtonAccentText}>Today</Text>
        </TouchableOpacity>

        <TouchableOpacity
          accessibilityRole="button"
          accessibilityLabel="Next day"
          onPress={() => navigateDate(1)}
          style={styles.bottomButton}
        >
          <Text style={styles.bottomButtonText}>Tomorrow</Text>
          <Ionicons name="chevron-forward" size={22} color={BRAND} />
        </TouchableOpacity>

        <TouchableOpacity
          accessibilityRole="button"
          accessibilityLabel="Pick a date"
          onPress={() => setShowCalendar(true)}
          style={styles.bottomButton}
        >
          <MaterialCommunityIcons
            name="calendar-today"
            size={20}
            color={BRAND}
          />
        </TouchableOpacity>
      </View>

      {selectedDate ? (
        <CalendarPicker
          visible={showCalendar}
          date={parseDateStr(selectedDate)}
          onSelect={pickDate}
          onDismiss={() => setShowCalendar(false)}
        />
      ) : null}
    </View>
  );
}

function renderSection(
  section: ReadingSection,
  theme: ThemeColors,
  dimmed = false,
) {
  const isGospel = section.type === "gospel";
  const unavailable = !section.available;

  return (
    <View
      key={section.type}
      style={[
        styles.section,
        isGospel && styles.gospelSection,
        dimmed && styles.sectionDimmed,
        isGospel && { borderLeftWidth: 3, borderLeftColor: BRAND },
      ]}
    >
      <Text
        style={[
          styles.sectionTitle,
          { color: theme.textSecondary },
          isGospel && styles.sectionTitleGospel,
        ]}
      >
        {section.title}
      </Text>

      {section.reference ? (
        <Text style={[styles.reference, { color: theme.text }]}>
          {section.reference}
        </Text>
      ) : null}

      {section.introduction ? (
        <Text style={[styles.introduction, { color: theme.textSecondary }]}>
          {"✝ " + section.introduction}
        </Text>
      ) : null}

      {section.response ? (
        <Text style={[styles.response, { color: theme.text }]}>
          {"R/. " + section.response}
        </Text>
      ) : null}

      {unavailable ? (
        <Text style={[styles.unavailable, { color: theme.textSecondary }]}>
          {section.type === "psalm"
            ? "Responsorial psalm is not available for this date yet."
            : "Reading text is not available for this date yet."}
        </Text>
      ) : (
        <Text
          style={[
            styles.scripture,
            { color: theme.text },
            dimmed && { opacity: 0.7 },
          ]}
          selectable
        >
          {section.text}
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  appBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.two,
    borderBottomWidth: 1,
    borderBottomColor: "#E5EAE6",
  },
  backButton: { padding: 8, marginRight: 6 },
  appBarTitle: {
    fontSize: 20,
    fontWeight: "700",
    flex: 1,
    textAlign: "center",
  },
  appBarRight: {
    flexDirection: "row",
    alignItems: "center",
  },
  bookmarkButton: { padding: 8, marginRight: 4 },
  languageButton: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 14,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  languageText: {
    fontSize: 13,
    color: "#6B7A70",
    fontWeight: "500",
  },
  languageTextActive: {
    color: BRAND,
    fontWeight: "700",
  },
  languageDot: {
    fontSize: 13,
    color: "#D8E0DA",
    marginHorizontal: 2,
  },
  scroll: {
    paddingHorizontal: Spacing.three,
    paddingTop: Spacing.two,
    paddingBottom: 112,
    maxWidth: MaxContentWidth,
    alignSelf: "center",
    width: "100%",
  },
  errorBanner: {
    flexDirection: "row",
    gap: 8,
    alignItems: "center",
    borderRadius: 12,
    padding: Spacing.two,
    marginBottom: Spacing.two,
    borderLeftWidth: 4,
    borderLeftColor: "#b91c1c",
  },
  fallbackBanner: {
    flexDirection: "row",
    gap: 8,
    alignItems: "center",
    borderRadius: 12,
    padding: Spacing.two,
    marginBottom: Spacing.two,
  },
  fallbackText: {
    fontSize: 13,
    lineHeight: 18,
    flexShrink: 1,
  },
  headerCard: {
    alignItems: "center",
    paddingVertical: Spacing.three,
    paddingHorizontal: Spacing.three,
    borderBottomWidth: 1,
    borderBottomColor: "#E5EAE6",
    marginBottom: Spacing.two,
  },
  weekday: {
    fontSize: 22,
    fontWeight: "700",
    color: BRAND,
  },
  date: {
    fontSize: 15,
    marginTop: 2,
  },
  celebrationRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 10,
    flexWrap: "wrap",
  },
  celebration: {
    fontSize: 17,
    fontWeight: "600",
  },
  rankBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
    marginLeft: 8,
  },
  rankText: {
    color: "#fff",
    fontSize: 11,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  colorRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 10,
  },
  colorDot: {
    width: 11,
    height: 11,
    borderRadius: 6,
    marginRight: 6,
    opacity: 0.85,
  },
  colorLine: {
    fontSize: 13,
    fontStyle: "italic",
  },
  weekLine: {
    fontSize: 14,
    marginTop: 6,
  },
  weekdayOfWeek: {
    fontSize: 13,
    fontStyle: "italic",
    marginTop: 2,
  },
  cycleLine: {
    fontSize: 13,
    marginTop: 6,
  },
  unverified: {
    fontSize: 11,
    color: "#F59E0B",
    marginTop: 6,
  },
  summaryCard: {
    borderRadius: 14,
    padding: Spacing.three,
    marginBottom: Spacing.two,
    borderWidth: 1,
  },
  summaryTitle: {
    fontSize: 13,
    fontWeight: "600",
    letterSpacing: 0.5,
    marginBottom: Spacing.two,
  },
  summaryRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: "#F1F5F2",
  },
  summaryLabel: {
    fontSize: 13,
  },
  summaryRef: {
    fontSize: 13,
    fontWeight: "600",
  },
  section: {
    marginBottom: Spacing.four,
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 1,
    textTransform: "uppercase",
    marginBottom: 6,
  },
  sectionTitleGospel: {
    fontSize: 13,
    color: BRAND,
  },
  gospelSection: {
    backgroundColor: "rgba(11,102,35,0.05)",
    borderRadius: 4,
    paddingHorizontal: Spacing.one,
    paddingVertical: Spacing.one,
  },
  sectionDimmed: {
    opacity: 0.6,
  },
  reference: {
    fontSize: 16,
    fontWeight: "600",
    marginBottom: 10,
  },
  introduction: {
    fontSize: 13,
    fontStyle: "italic",
    marginBottom: 10,
    lineHeight: 19,
  },
  response: {
    fontSize: 15,
    fontWeight: "700",
    marginBottom: 10,
    lineHeight: 21,
  },
  scripture: {
    fontFamily: Fonts.serif,
    fontSize: 18,
    lineHeight: 31,
    textAlign: "left",
  },
  unavailable: {
    fontStyle: "italic",
    fontSize: 14,
    lineHeight: 20,
  },
  emptyCard: {
    alignItems: "center",
    padding: Spacing.three,
    marginTop: Spacing.four,
    gap: 10,
  },
  emptyText: {
    fontSize: 15,
    textAlign: "center",
    lineHeight: 22,
  },
  fallbackBlock: {
    marginTop: Spacing.two,
    borderTopWidth: 1,
    borderTopColor: "#E5EAE6",
    paddingTop: Spacing.two,
  },
  fallbackBlockTitle: {
    fontSize: 13,
    fontWeight: "700",
    marginBottom: 8,
  },
  reflectionCard: {
    borderRadius: 14,
    padding: Spacing.three,
    marginTop: Spacing.two,
    borderWidth: 1,
  },
  reflection: {
    fontSize: 14,
    fontStyle: "italic",
    lineHeight: 21,
  },
  prayerCard: {
    backgroundColor: "#F0F7FF",
    borderRadius: 14,
    padding: Spacing.three,
    marginTop: Spacing.two,
    borderWidth: 1,
    borderColor: "#D0E4FF",
  },
  prayer: {
    fontSize: 15,
    lineHeight: 24,
    marginTop: 4,
  },
  bottomBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: Spacing.three,
    paddingVertical: 12,
    borderTopWidth: 1,
    paddingBottom: 16,
  },
  bottomButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  bottomButtonText: {
    fontSize: 15,
    color: BRAND,
    fontWeight: "600",
  },
  bottomButtonAccent: {
    backgroundColor: "#EAF4ED",
    borderRadius: 16,
  },
  bottomButtonAccentText: {
    color: BRAND,
    fontWeight: "800",
    fontSize: 15,
  },
});
