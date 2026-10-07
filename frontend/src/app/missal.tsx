/**
 * The Catholic digital missal: the Order of Mass for a liturgical day.
 *
 * This screen presents the complete structure of the Mass for the selected
 * celebration and links each Scripture reading to the existing reading screen
 * (`/reading-detail`), which is the single place reading *text* is rendered.
 * It deliberately does NOT duplicate Scripture text here.
 *
 * Single source of truth (no invention):
 *   - Liturgical calendar header:  GET /api/v1/liturgy/date/{date}
 *   - Scripture readings:          GET /api/readings/{date}?language=...}
 * These are aggregated by `readingsService.getMissalByDate`, which owns the
 * cache-first / offline policy. What the backend does not supply is shown as a
 * clear "verified content unavailable" state -- never guessed, never a
 * fabricated Roman Missal prayer (the project holds no licence for the
 * Ordinary/Formulary prayers such as the Collect, Eucharistic Prayer, the
 * Lord's Prayer as prayed, etc.).
 *
 * The only static strings in this file are:
 *   - canonical Order-of-Mass *structure* labels (USCCB/GIRM public titles), and
 *   - a fixed unavailable-state notice.
 * No liturgical prayer text, no Scripture, no hard-coded 2026 readings.
 */
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import {
  Alert,
  Platform,
  RefreshControl,
  ScrollView,
  Share,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons, MaterialCommunityIcons } from "@expo/vector-icons";
import AsyncStorage from "@react-native-async-storage/async-storage";

import { useTheme } from "@/hooks/use-theme";
import { liturgicalAccent } from "@/constants/choirTheme";
import {
  DEFAULT_LANGUAGE,
  LITURGY_REGION,
  MissalLoadResult,
  ReadingLanguage,
  ReadingSection,
  getLanguage,
  getMissalByDate,
  refreshMissal,
  setLanguage,
} from "@/services/readingsService";
import { ReadingsCache } from "@/services/readingsCache";
import { favoriteService } from "@/services/favoriteService";
import { ErrorState, LoadingState } from "@/components/ScreenStates";
import { CalendarPicker } from "@/components/CalendarPicker";
import {
  formatKenyaDate,
  kenyaDateString,
  shiftCalendarDate,
} from "@/utils/calendar";

const BRAND = "#0B6623";
const GOLD = "#A8801C";
const BORDER = "#E5EAE6";

/** Canonical Order-of-Mass structure labels (public titles, not prayer text). */
const UNAVAILABLE_LABEL = {
  missing: "Content unavailable",
  reason: "The project does not hold an authorised Roman Missal text for this rite.",
  remedy: "It will appear here when licensed content is provided.",
} as const;

type RiteDef = { key: string; label: string };

const INTRODUCTORY_RITES: RiteDef[] = [
  { key: "entrance", label: "Entrance" },
  { key: "greeting", label: "Greeting" },
  { key: "penitential", label: "Penitential Act" },
  { key: "gloria", label: "Gloria" },
  { key: "collect", label: "Collect" },
];

const EUCHARISTIC_PARTS: RiteDef[] = [
  { key: "presentation", label: "Presentation of the Gifts" },
  { key: "offerings", label: "Prayer over the Offerings" },
  { key: "eucharistic_prayer", label: "Eucharistic Prayer" },
  { key: "preface", label: "Preface" },
  { key: "sanctus", label: "Sanctus (Holy, Holy, Holy)" },
  { key: "acclamation", label: "Memorial Acclamation" },
  { key: "amen", label: "Great Amen" },
];

const COMMUNION_PARTS: RiteDef[] = [
  { key: "lords_prayer", label: "Lord's Prayer" },
  { key: "sign_of_peace", label: "Sign of Peace" },
  { key: "lamb_of_god", label: "Lamb of God (Agnus Dei)" },
  { key: "communion", label: "Communion" },
  { key: "communion_antiphon", label: "Communion Antiphon" },
  { key: "prayer_after_communion", label: "Prayer after Communion" },
];

const CONCLUDING_PARTS: RiteDef[] = [
  { key: "announcements", label: "Announcements (when needed)" },
  { key: "farewell", label: "Greeting" },
  { key: "blessing", label: "Blessing" },
  { key: "dismissal", label: "Dismissal (Go forth, the Mass is ended)" },
];

const JURISDICTION_LABELS: Record<string, string> = {
  KE: "Kenya",
  TZ: "Tanzania",
  NG: "Nigeria",
  US: "United States",
  GB: "Great Britain",
};

function parseDateStr(dateStr: string): Date {
  const parts = dateStr.split("-").map(Number);
  const [year, month, day] = parts as [number, number, number];
  return new Date(Date.UTC(year, month - 1, day, 12));
}

function weekdayLong(dateStr: string, language: ReadingLanguage): string {
  const swahili = ["Jumapili", "Jumatatu", "Jumanne", "Junnei", "Alhamisi", "Ijumaa", "Jumamosi"];
  const english = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  const names = language === "Kiswahili" ? swahili : english;
  return names[parseDateStr(dateStr).getUTCDay()];
}

function ordinal(n: number): string {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return `${n}${s[(v - 20) % 10] || s[v] || s[0]}`;
}

function capitalize(value: string | null | undefined): string {
  if (!value) return "";
  return value.charAt(0).toUpperCase() + value.slice(1);
}

const COLOR_HEX: Record<string, string> = {
  green: "#16a34a",
  white: "#cbd5e1",
  red: "#b91c1c",
  purple: "#6b21a8",
  violet: "#6b21a8",
  rose: "#d97706",
  gold: "#d97706",
  black: "#1f2937",
};

function colorHexFor(name: string | null | undefined): string {
  if (!name) return BRAND;
  return COLOR_HEX[name.trim().toLowerCase()] ?? BRAND;
}

function rankBadgeColor(rank: string | null): string {
  if (!rank) return BRAND;
  const r = rank.toLowerCase();
  if (r.includes("holy day") || r.includes("solemnity")) return "#A32018";
  if (r.includes("feast")) return "#7C3A3A";
  if (r.includes("sunday")) return BRAND;
  if (r.includes("memorial")) return "#6B21A8";
  return "#6B7A70";
}

function downloadFlag(date: string, language: ReadingLanguage): string {
  return `missal_downloaded_${date}_${language}`;
}

type OfflineState = "downloaded" | "cached" | "online" | "unavailable";

function MissalAppBar({
  onBack,
  bookmarked,
  canBookmark,
  onToggleBookmark,
  downloading,
  onDownload,
  onShare,
  language,
  onToggleLanguage,
}: {
  onBack: () => void;
  bookmarked: boolean | null;
  canBookmark: boolean;
  onToggleBookmark: () => void;
  downloading: boolean;
  onDownload: () => void;
  onShare: () => void;
  language: ReadingLanguage;
  onToggleLanguage: () => void;
}) {
  const theme = useTheme();
  return (
    <View
      style={[
        styles.appBar,
        { backgroundColor: theme.background, borderBottomColor: theme.backgroundElement },
      ]}
    >
      <TouchableOpacity accessibilityRole="button" accessibilityLabel="Back" onPress={onBack} style={styles.iconBtn}>
        <Ionicons name="chevron-back" size={24} color={BRAND} />
      </TouchableOpacity>

      <Text style={[styles.appBarTitle, { color: theme.text }]}>Missal</Text>

      <View style={styles.appBarRight}>
        <TouchableOpacity
          accessibilityRole="button"
          accessibilityState={{ selected: canBookmark && bookmarked === true }}
          accessibilityLabel={canBookmark && bookmarked ? "Remove bookmark" : "Add bookmark"}
          disabled={!canBookmark}
          onPress={onToggleBookmark}
          style={styles.iconBtn}
        >
          <Ionicons
            name={canBookmark && bookmarked ? "bookmark" : "bookmark-outline"}
            size={22}
            color={canBookmark ? BRAND : theme.textSecondary}
          />
        </TouchableOpacity>

        <TouchableOpacity
          accessibilityRole="button"
          accessibilityLabel="Download for offline"
          disabled={downloading}
          onPress={onDownload}
          style={styles.iconBtn}
        >
          <Ionicons name="download" size={20} color={downloading ? theme.textSecondary : BRAND} />
        </TouchableOpacity>

        <TouchableOpacity accessibilityRole="button" accessibilityLabel="Share" onPress={onShare} style={styles.iconBtn}>
          <Ionicons name="share-outline" size={20} color={BRAND} />
        </TouchableOpacity>

        <TouchableOpacity
          accessibilityRole="button"
          accessibilityLabel="Switch language"
          onPress={onToggleLanguage}
          style={[styles.iconBtn, styles.langBtn]}
        >
          <Text style={[styles.langText, { color: theme.text }]}>{language === "English" ? "EN" : "SW"}</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

function StatusChip({ available }: { available: boolean }) {
  const color = available ? BRAND : "#B91C1C";
  const label = available ? "Available" : "Unavailable";
  const iconName = available ? "cloud-check" : "alert-circle";
  return (
    <View style={[styles.chip, { backgroundColor: available ? "#EAF4ED" : "#FDECEA", borderColor: BORDER }]}>
      <MaterialCommunityIcons name={iconName} size={12} color={color} />
      <Text style={[styles.chipText, { color: color }]}>{label}</Text>
    </View>
  );
}

function RiteRow({ label, available = false }: { label: string; available?: boolean }) {
  const theme = useTheme();
  return (
    <View style={[styles.riteRow, { borderBottomColor: theme.backgroundElement }]}>
      <Text style={[styles.riteLabel, { color: theme.text }]}>{label}</Text>
      <StatusChip available={available} />
    </View>
  );
}

function UnavailableNote() {
  const theme = useTheme();
  return (
    <View style={styles.unavailableNote}>
      <Text style={[styles.unavailableLabel, { color: "#B91C1C" }]}>{UNAVAILABLE_LABEL.missing}</Text>
      <Text style={[styles.unavailableReason, { color: theme.textSecondary }]}>{UNAVAILABLE_LABEL.reason}</Text>
      <Text style={[styles.unavailableRemedy, { color: theme.textSecondary }]}>{UNAVAILABLE_LABEL.remedy}</Text>
    </View>
  );
}

function OverviewCard({
  header,
  jurisdiction,
}: {
  header: MissalLoadResult["data"]["header"] | null;
  jurisdiction: string;
}) {
  const theme = useTheme();
  const rows: { label: string; value: string }[] = [
    { label: "Celebration", value: header?.celebration ?? "—" },
    { label: "Rank", value: header?.rank ?? "—" },
    { label: "Season", value: header?.season ?? "—" },
    { label: "Liturgical colour", value: capitalize(header?.liturgicalColor) || "—" },
    { label: "Liturgical year", value: header?.sundayCycle ? `Year ${header.sundayCycle}` : "—" },
    { label: "Weekday cycle", value: header?.weekdayCycle ?? "—" },
    { label: "Week", value: header?.week != null ? ordinal(header.week) : "—" },
    { label: "Jurisdiction / proper calendar", value: `${jurisdiction} (${LITURGY_REGION})` },
  ];
  return (
    <View style={styles.detailGrid}>
      {rows.map((row) => (
        <View key={row.label} style={styles.detailRow}>
          <Text style={[styles.detailLabel, { color: theme.textSecondary }]}>{row.label}</Text>
          <Text style={[styles.detailValue, { color: theme.text }]}>{row.value}</Text>
        </View>
      ))}
    </View>
  );
}

function WordCard({
  sections,
  date,
  missal,
}: {
  sections: ReadingSection[];
  date: string;
  missal: MissalLoadResult | null;
}) {
  const router = useRouter();
  const theme = useTheme();

  const openReadings = () => {
    router.push({ pathname: "/reading-detail", params: { date } });
  };

  if (sections.length === 0) {
    return (
      <View style={styles.wordEmpty}>
        <Text style={[styles.wordEmptyText, { color: theme.textSecondary }]}>
          {missal?.notFound
            ? "The liturgical calendar lists references for this date, but no reading text is published yet."
            : "The readings for this date are being prepared."}
        </Text>
        <Text style={[styles.wordEmptySub, { color: theme.textSecondary }]}>
          Open the Readings view to see the full Scripture once it is published.
        </Text>
      </View>
    );
  }

  return (
    <View>
      {sections.map((section) => (
        <TouchableOpacity
          key={section.type}
          style={[styles.wordRow, { borderBottomColor: theme.backgroundElement }]}
          onPress={openReadings}
          accessibilityRole="button"
        >
          <View style={styles.wordRowText}>
            <Text style={[styles.wordSectionTitle, { color: theme.text }]}>{section.title}</Text>
            {section.reference ? (
              <Text style={[styles.wordReference, { color: theme.textSecondary }]}>{section.reference}</Text>
            ) : null}
            {section.available ? (
              <Text style={[styles.wordHint, { color: theme.textSecondary }]}>
                Text available in Readings view
              </Text>
            ) : (
              <Text style={[styles.wordHint, { color: theme.textSecondary }]}>
                Reference available; text not yet published
              </Text>
            )}
          </View>
          <Ionicons name="chevron-forward" size={20} color={theme.textSecondary} />
        </TouchableOpacity>
      ))}

      <View style={styles.wordActions}>
        <TouchableOpacity
          style={[styles.primaryBtn, { backgroundColor: BRAND }]}
          onPress={openReadings}
          accessibilityRole="button"
        >
          <Text style={styles.primaryBtnText}>Open full readings</Text>
        </TouchableOpacity>
      </View>

      <Text style={[styles.wordMeta, { color: theme.textSecondary }]}>
        Scripture text, the Gospel Acclamation, the reflection and the day&apos;s
        prayer are shown in the Readings view rather than duplicated here.
      </Text>
    </View>
  );
}

function NotesCard({
  header,
  missal,
  jurisdiction,
  cachedAt,
  offlineState,
}: {
  header: MissalLoadResult["data"]["header"] | null;
  missal: MissalLoadResult | null;
  jurisdiction: string;
  cachedAt: string | null;
  offlineState: OfflineState;
}) {
  const theme = useTheme();
  const rows: { label: string; value: string }[] = [
    { label: "Celebration rank", value: header?.rank ?? "—" },
    {
      label: "Calendar source",
      value: header?.source
        ? `${header.source} (${jurisdiction})`
        : `Kenya (${LITURGY_REGION}) proper calendar`,
    },
    { label: "Verification", value: header?.verificationStatus ?? "unverified" },
    { label: "Liturgical year / cycle", value: `${header?.sundayCycle ?? "—"} / ${header?.weekdayCycle ?? "—"}` },
    {
      label: "Offline state",
      value:
        offlineState === "unavailable"
          ? "Unavailable"
          : offlineState === "downloaded"
            ? "Downloaded (offline)"
            : offlineState === "cached"
              ? "Cached (offline-capable)"
              : "Online only",
    },
  ];
  if (cachedAt) {
    rows.push({
      label: "Last cached",
      value: new Date(cachedAt).toLocaleDateString(undefined, { dateStyle: "medium" }),
    });
  }
  return (
    <View style={styles.detailGrid}>
      {rows.map((row) => (
        <View key={row.label} style={styles.detailRow}>
          <Text style={[styles.detailLabel, { color: theme.textSecondary }]}>{row.label}</Text>
          <Text style={[styles.detailValue, { color: theme.text }]}>{row.value}</Text>
        </View>
      ))}
      {missal?.notFound ? (
        <View style={styles.detailRow}>
          <Text style={[styles.detailLabel, { color: theme.textSecondary }]}>Authorized reading text</Text>
          <Text style={[styles.detailValue, { color: "#B91C1C" }]}>Not published for this date</Text>
        </View>
      ) : null}
    </View>
  );
}

function SectionCard({
  title,
  defaultState = "closed",
  accent,
  summary,
  children,
}: {
  title: string;
  defaultState?: "open" | "closed";
  accent?: string;
  summary?: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultState === "open");
  const theme = useTheme();
  const tint = accent ?? BRAND;
  return (
    <View
      style={[
        styles.card,
        { backgroundColor: theme.background, borderColor: theme.backgroundElement },
      ]}
    >
      <TouchableOpacity
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        onPress={() => setOpen((v) => !v)}
        style={[styles.cardHeader, { borderBottomColor: theme.backgroundElement }]}
      >
        <View style={[styles.colorAccent, { backgroundColor: tint }]} />
        <Text style={[styles.cardTitle, { color: theme.text }]}>{title}</Text>
        {summary ? <Text style={[styles.cardSummary, { color: theme.textSecondary }]}>{summary}</Text> : null}
        <MaterialCommunityIcons
          name={open ? "chevron-down" : "chevron-right"}
          size={22}
          color={theme.textSecondary}
          style={styles.chevron}
        />
      </TouchableOpacity>
      {open ? <View style={styles.cardBody}>{children}</View> : null}
    </View>
  );
}

function OfflineBanner({ state }: { state: OfflineState }) {
  const theme = useTheme();
  const iconMap: Record<OfflineState, { name: string; color: string }> = {
    unavailable: { name: "alert-circle", color: "#B91C1C" },
    cached: { name: "cloud-check", color: BRAND },
    downloaded: { name: "download", color: BRAND },
    online: { name: "cloud-upload", color: BRAND },
  };
  const cfg = iconMap[state];
  const bg =
    state === "unavailable"
      ? "#FDECEA"
      : state === "cached"
        ? "#FEF3C7"
        : state === "downloaded"
          ? "#E6F1E8"
          : "#F0F7FF";
  return (
    <View style={[styles.banner, { backgroundColor: bg, borderColor: theme.backgroundElement }]}>
      <View style={styles.bannerRow}>
        <Ionicons name={cfg.name as never} size={16} color={cfg.color} />
        <Text style={[styles.bannerText, { color: theme.text }]}>{bannerText(state)}</Text>
      </View>
    </View>
  );
}

function bannerText(state: OfflineState): string {
  if (state === "unavailable") return "No liturgical data available for this date.";
  if (state === "cached") return "Showing cached data (works offline).";
  if (state === "downloaded") return "Available offline (saved for offline use).";
  return "Online — Order of Mass";
}

function useDownloadStatus(date: string, language: ReadingLanguage): { downloaded: boolean; cachedAt: string | null } {
  const [downloaded, setDownloaded] = useState(false);
  const [cachedAt, setCachedAt] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    void AsyncStorage.getItem(downloadFlag(date, language)).then((flag) => {
      if (active) setDownloaded(flag === "1");
    });
    void ReadingsCache.get(date, language).then((cached) => {
      if (active) setCachedAt(cached?.cached_at ?? null);
    });
    return () => {
      active = false;
    };
  }, [date, language]);
  return { downloaded, cachedAt };
}

export default function MissalScreen() {
  const { date: dateParam } = useLocalSearchParams<{ date?: string }>();
  const router = useRouter();
  const theme = useTheme();
  const defaultDate = kenyaDateString(new Date());

  const [date, setDate] = useState<string>(dateParam ?? defaultDate);
  const [language, setLanguageState] = useState<ReadingLanguage>(DEFAULT_LANGUAGE);
  const [missal, setMissal] = useState<MissalLoadResult | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [showCalendar, setShowCalendar] = useState<boolean>(false);
  const [bookmarked, setBookmarked] = useState<boolean | null>(null);
  const [downloading, setDownloading] = useState<boolean>(false);

  const activeTokenRef = useRef(0);
  const { downloaded, cachedAt } = useDownloadStatus(date, language);

  useEffect(() => {
    void getLanguage().then((lang) => setLanguageState(lang));
  }, []);

  const load = useCallback(
    async (dateStr: string, lang: ReadingLanguage) => {
      const token = ++activeTokenRef.current;
      setLoading(true);
      setError(null);
      try {
        const result = await getMissalByDate(dateStr, lang);
        if (activeTokenRef.current !== token) return;
        setMissal(result);
        setError(null);
      } catch {
        if (activeTokenRef.current !== token) return;
        setError("Could not load the missal. Check your connection and try again.");
        setMissal(null);
      } finally {
        if (activeTokenRef.current === token) setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    void Promise.resolve().then(() => load(date, language));
  }, [load, date, language]);

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
          favs.some((f) => f.resource_type === "reading" && f.target_resource_id === readingId),
        );
      })
      .catch(() => {
        if (active) setBookmarked(null);
      });
    return () => {
      active = false;
    };
  }, [missal?.data.id]);

  const refresh = async () => {
    setRefreshing(true);
    try {
      const result = await refreshMissal(date, language);
      setMissal(result);
      setError(null);
    } catch {
      setError("Could not refresh the missal. Check your connection and try again.");
    } finally {
      setRefreshing(false);
    }
  };

  const toggleBookmark = () => {
    const readingId = missal?.data.id;
    if (!readingId) return;
    if (bookmarked) {
      void favoriteService
        .getFavoritesOptional()
        .then((favs) => {
          const match = favs.find(
            (f) => f.resource_type === "reading" && f.target_resource_id === readingId,
          );
          if (match) return favoriteService.deleteFavorite(match.id);
          return Promise.resolve();
        })
        .then(() => setBookmarked(false))
        .catch(() => Alert.alert("Could not update bookmark", "Please try again."));
    } else {
      void favoriteService
        .createFavorite("reading", readingId)
        .then(() => setBookmarked(true))
        .catch((e: { response?: { status?: number } }) => {
          if (e?.response?.status === 401) {
            Alert.alert("Sign in to bookmark", "Save this Mass to your bookmarks by signing in.", [
              { text: "Cancel", style: "cancel" },
              { text: "Sign in", onPress: () => router.push("/login" as never) },
            ]);
          } else {
            Alert.alert("Could not update bookmark", "Please try again.");
          }
        });
    }
  };

  const downloadForOffline = async () => {
    setDownloading(true);
    try {
      // refreshMissal re-hits the network and re-populates the caches.
      await refreshMissal(date, language);
    } catch {
      // fall through: a cached copy may still satisfy "download".
    }
    const cached = await ReadingsCache.get(date, language);
    if (!cached && !missal?.data.header) {
      await AsyncStorage.removeItem(downloadFlag(date, language));
      Alert.alert("Download failed", "Connect to the internet to download the missal.");
    } else {
      await AsyncStorage.setItem(downloadFlag(date, language), "1");
      Alert.alert("Saved offline", "This day's missal and readings are now available offline.");
    }
    setDownloading(false);
  };

  const shareMissal = async () => {
    const header = missal?.data.header;
    const message = [
      header?.celebration ? `${header.celebration} (${header.date})` : header?.date ?? date,
      header?.rank ?? null,
      "Catholic Readings & Choir Resources — Order of Mass",
    ]
      .filter(Boolean)
      .join("\n");
    if (Platform.OS !== "web") {
      try {
        const result = await Share.share({ title: "Missal", message });
        if (result?.action === "dismissedAction") return;
        return;
      } catch {
        // fall through to a plain alert
      }
    }
    Alert.alert("Order of Mass", message);
  };

  const toggleLanguage = () => {
    const next: ReadingLanguage = language === "English" ? "Kiswahili" : "English";
    void setLanguage(next);
    setLanguageState(next);
  };

  const pickDate = (picked: Date) => {
    setShowCalendar(false);
    setDate(kenyaDateString(picked));
  };

  // ----- Derived values -----
  const offlineState: OfflineState = (() => {
    if (!missal) return "unavailable";
    if (missal.notFound && (!missal.data.sections || missal.data.sections.length === 0)) {
      return "unavailable";
    }
    if (downloaded) return "downloaded";
    if (missal.offline) return "cached";
    if (missal.fromCache) return "cached";
    return "online";
  })();

  const header = missal?.data.header ?? null;
  const sections = missal?.data.sections ?? [];
  const colorHex = colorHexFor(header?.liturgicalColor);
  const accent = liturgicalAccent(header?.liturgicalColor ?? null).accent;
  const jurisdiction = JURISDICTION_LABELS[LITURGY_REGION] ?? LITURGY_REGION;

  if (loading && !missal) {
    return (
      <View style={[styles.root, { backgroundColor: theme.background }]}>
        <MissalAppBar
          onBack={() => router.back()}
          bookmarked={null}
          canBookmark={false}
          onToggleBookmark={() => {}}
          downloading={false}
          onDownload={() => {}}
          onShare={() => {}}
          language={language}
          onToggleLanguage={toggleLanguage}
        />
        <LoadingState label="Loading the Order of Mass…" />
      </View>
    );
  }

  if (error && !missal) {
    return (
      <View style={[styles.root, { backgroundColor: theme.background }]}>
        <MissalAppBar
          onBack={() => router.back()}
          bookmarked={null}
          canBookmark={false}
          onToggleBookmark={() => {}}
          downloading={false}
          onDownload={() => {}}
          onShare={() => {}}
          language={language}
          onToggleLanguage={toggleLanguage}
        />
        <ErrorState message={error} onRetry={() => void load(date, language)} retryLabel="Try again" />
      </View>
    );
  }

  return (
    <View style={[styles.root, { backgroundColor: theme.background }]}>
      <MissalAppBar
        onBack={() => router.back()}
        bookmarked={bookmarked}
        canBookmark={missal?.data.id != null}
        onToggleBookmark={toggleBookmark}
        downloading={downloading}
        onDownload={downloadForOffline}
        onShare={shareMissal}
        language={language}
        onToggleLanguage={toggleLanguage}
      />

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={BRAND} colors={[BRAND]} />
        }
      >
        <OfflineBanner state={offlineState} />
        {cachedAt ? (
          <Text style={[styles.cachedAtText, { color: theme.textSecondary }]}>
            Cached on {new Date(cachedAt).toLocaleDateString(undefined, { dateStyle: "medium" })}
          </Text>
        ) : null}

        {/* Kiswahili fallback notice */}
        {missal?.notFound && language === "Kiswahili" && (missal.englishFallback || sections.length === 0) ? (
          <View
            style={[styles.banner, { backgroundColor: "#FEF3C7", borderColor: theme.backgroundElement }]}
          >
            <View style={styles.bannerRow}>
              <Ionicons name="language" size={16} color={BRAND} />
              <Text style={[styles.bannerText, { color: theme.text }]}>
                {missal.englishFallback
                  ? "Kiswahili text is not available for this date. Open the Readings view for available English content."
                  : "Kiswahili text is not available for this date."}
              </Text>
            </View>
          </View>
        ) : null}

        {/* Date navigation */}
        <View
          style={[
            styles.dateNav,
            { backgroundColor: theme.background, borderColor: theme.backgroundElement },
          ]}
        >
          <TouchableOpacity
            accessibilityRole="button"
            accessibilityLabel="Previous day"
            onPress={() => setDate(shiftCalendarDate(date, -1))}
            style={styles.dateBtn}
          >
            <Ionicons name="chevron-back" size={24} color={BRAND} />
          </TouchableOpacity>

          <TouchableOpacity
            accessibilityRole="button"
            accessibilityLabel="Pick a date"
            onPress={() => setShowCalendar(true)}
            style={[styles.dateBtn, styles.dateLabelBtn]}
          >
            <MaterialCommunityIcons name="calendar-today" size={18} color={BRAND} />
            <Text style={[styles.dateLabel, { color: theme.text }]}>{formatKenyaDate(date)}</Text>
          </TouchableOpacity>

          <TouchableOpacity
            accessibilityRole="button"
            accessibilityLabel="Next day"
            onPress={() => setDate(shiftCalendarDate(date, 1))}
            style={styles.dateBtn}
          >
            <Ionicons name="chevron-forward" size={24} color={BRAND} />
          </TouchableOpacity>
        </View>

        {/* Mass header */}
        <View
          style={[styles.headerCard, { backgroundColor: theme.background, borderColor: theme.backgroundElement }]}
        >
          <View style={[styles.headerAccent, { backgroundColor: colorHex }]} />
          <View style={styles.headerGrid}>
            <Text style={[styles.celebration, { color: theme.text }]}>
              {header?.celebration ?? weekdayLong(date, language)}
            </Text>
            {header?.rank ? (
              <View style={[styles.rankBadge, { backgroundColor: rankBadgeColor(header.rank) }]}>
                <Text style={styles.rankText}>{header.rank}</Text>
              </View>
            ) : null}

            <Text style={[styles.metaText, { color: theme.textSecondary }]}>
              {weekdayLong(date, language)}, {formatKenyaDate(date)}
            </Text>

            <View style={styles.metaRow}>
              <View style={[styles.dot, { backgroundColor: colorHex }]} />
              <Text style={[styles.metaText, { color: theme.textSecondary }]}>
                {capitalize(header?.liturgicalColor) || "Colour not specified"}
              </Text>
            </View>

            <View style={styles.metaRow}>
              <Text style={[styles.metaText, { color: theme.text }]}>Season: {header?.season ?? "—"}</Text>
              {header?.week != null ? (
                <Text style={[styles.metaText, { color: theme.text }]}>Week {header.week}</Text>
              ) : null}
            </View>

            <View style={styles.metaRow}>
              <Text style={[styles.metaText, { color: theme.text }]}>
                Liturgical year: {header?.sundayCycle ?? "—"}
              </Text>
              <Text style={[styles.metaText, { color: theme.textSecondary }]}>
                ({header?.weekdayCycle ?? "—"})
              </Text>
            </View>

            <Text style={[styles.metaText, { color: theme.textSecondary }]}>
              Jurisdiction: {jurisdiction} ({LITURGY_REGION})
            </Text>

            {header?.verificationStatus && header.verificationStatus !== "verified" ? (
              <View style={[styles.rankBadge, { backgroundColor: "#FEF3C7" }]}>
                <Text style={[styles.rankText, { color: "#B91C1C" }]}>
                  {capitalize(header.verificationStatus)}
                </Text>
              </View>
            ) : null}
          </View>
        </View>

        <SectionCard title="Mass overview" defaultState="closed" accent={accent}>
          <OverviewCard header={header} jurisdiction={jurisdiction} />
        </SectionCard>

        <SectionCard title="Introductory Rites" defaultState="closed" accent={colorHex}>
          {INTRODUCTORY_RITES.map((rite) => (
            <RiteRow key={rite.key} label={rite.label} available={false} />
          ))}
          <UnavailableNote />
        </SectionCard>

        <SectionCard
          title="Liturgy of the Word"
          defaultState="open"
          accent={BRAND}
          summary={
            sections.length > 0
              ? `${sections.length} reading${sections.length === 1 ? "" : "s"} listed`
              : "No reading text yet"
          }
        >
          <WordCard sections={sections} date={date} missal={missal} />
        </SectionCard>

        <SectionCard title="Gospel Acclamation" defaultState="closed" accent={colorHex}>
          {missal?.data.gospelAcclamation ? (
            <Text style={[styles.prayerText, { color: theme.text }]} selectable>
              {missal.data.gospelAcclamation}
            </Text>
          ) : (
            <UnavailableNote />
          )}
        </SectionCard>

        <SectionCard title="Homily / reflection" defaultState="closed" accent={colorHex}>
          {missal?.data.reflection ? (
            <Text style={[styles.prayerText, { color: theme.text }]} selectable>
              {missal.data.reflection}
            </Text>
          ) : (
            <UnavailableNote />
          )}
        </SectionCard>

        <SectionCard title="Profession of Faith" defaultState="closed" accent={colorHex}>
          <UnavailableNote />
        </SectionCard>

        <SectionCard title="Universal Prayer" defaultState="closed" accent={colorHex}>
          <UnavailableNote />
        </SectionCard>

        <SectionCard title="Liturgy of the Eucharist" defaultState="closed" accent={colorHex}>
          {EUCHARISTIC_PARTS.map((rite) => (
            <RiteRow key={rite.key} label={rite.label} available={false} />
          ))}
          <UnavailableNote />
        </SectionCard>

        <SectionCard title="Communion Rite" defaultState="closed" accent={colorHex}>
          {COMMUNION_PARTS.map((rite) => (
            <RiteRow key={rite.key} label={rite.label} available={false} />
          ))}
          <UnavailableNote />
        </SectionCard>

        <SectionCard title="Concluding Rites" defaultState="closed" accent={colorHex}>
          {CONCLUDING_PARTS.map((rite) => (
            <RiteRow key={rite.key} label={rite.label} available={false} />
          ))}
          <UnavailableNote />
        </SectionCard>

        <SectionCard title="Liturgical notes" defaultState="closed" accent={GOLD}>
          <NotesCard
            header={header}
            missal={missal}
            jurisdiction={jurisdiction}
            cachedAt={cachedAt}
            offlineState={offlineState}
          />
        </SectionCard>

        <View style={styles.footerPad} />
      </ScrollView>

      <CalendarPicker
        visible={showCalendar}
        date={parseDateStr(date)}
        onSelect={pickDate}
        onDismiss={() => setShowCalendar(false)}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  scrollContent: { paddingBottom: 24 },
  appBar: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderBottomWidth: 1,
  },
  iconBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
  },
  appBarTitle: { fontSize: 20, fontWeight: "700", flex: 1, textAlign: "center" },
  appBarRight: { flexDirection: "row", alignItems: "center" },
  langBtn: { backgroundColor: "#EAF4ED", borderRadius: 14, paddingHorizontal: 8 },
  langText: { fontSize: 13, fontWeight: "700" },
  banner: {
    marginHorizontal: 16,
    marginTop: 12,
    borderRadius: 12,
    borderWidth: 1,
    padding: 10,
  },
  bannerRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  bannerText: { fontSize: 13, flexShrink: 1, lineHeight: 18 },
  cachedAtText: { marginHorizontal: 16, marginTop: 4, fontSize: 12, color: "#666" },
  dateNav: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    marginHorizontal: 16,
    marginTop: 12,
    borderRadius: 14,
    padding: 8,
    borderWidth: 1,
  },
  dateBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#EAF4ED",
  },
  dateLabelBtn: { flex: 1, flexDirection: "row", gap: 6 },
  dateLabel: { fontSize: 15, fontWeight: "600", color: BRAND },
  headerCard: {
    marginHorizontal: 16,
    marginTop: 12,
    borderRadius: 16,
    borderWidth: 1,
    padding: 14,
  },
  headerAccent: { position: "absolute", left: 0, top: 0, bottom: 0, width: 6 },
  headerGrid: { flex: 1 },
  celebration: { fontSize: 22, fontWeight: "800", marginBottom: 4 },
  rankBadge: {
    alignSelf: "flex-start",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
    marginTop: 6,
  },
  rankText: { fontSize: 11, fontWeight: "700", color: "#FFFFFF" },
  metaRow: { flexDirection: "row", alignItems: "center", marginTop: 6, gap: 6 },
  metaText: { fontSize: 13, color: "#444" },
  dot: { width: 12, height: 12, borderRadius: 6 },
  card: { marginHorizontal: 16, marginTop: 12, borderRadius: 16, borderWidth: 1, overflow: "hidden" },
  cardHeader: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 12,
    paddingVertical: 12,
  },
  colorAccent: { width: 4, height: 26, borderRadius: 2, marginRight: 8 },
  cardTitle: { fontSize: 17, fontWeight: "700", flex: 1 },
  cardSummary: { fontSize: 12, color: "#777", marginRight: 8 },
  chevron: { marginLeft: 6 },
  cardBody: { paddingHorizontal: 14, paddingVertical: 10 },
  chip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
    borderWidth: 1,
    alignSelf: "flex-start",
  },
  chipText: { fontSize: 11, fontWeight: "700" },
  riteRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 8,
    borderBottomWidth: 1,
  },
  riteLabel: { fontSize: 14, fontWeight: "600" },
  unavailableNote: { marginTop: 10, gap: 4 },
  unavailableLabel: { fontSize: 13, fontWeight: "700" },
  unavailableReason: { fontSize: 12, lineHeight: 17 },
  unavailableRemedy: { fontSize: 12, lineHeight: 17, fontStyle: "italic" },
  detailGrid: { gap: 4 },
  detailRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 6,
  },
  detailLabel: { fontSize: 12, color: "#777" },
  detailValue: { fontSize: 13, fontWeight: "500", color: "#222", maxWidth: "60%" },
  wordRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 10,
    borderBottomWidth: 1,
  },
  wordRowText: { flex: 1, marginRight: 8 },
  wordSectionTitle: { fontSize: 15, fontWeight: "700", marginBottom: 2 },
  wordReference: { fontSize: 12, color: "#777", marginBottom: 2 },
  wordHint: { fontSize: 11, color: "#777", fontStyle: "italic" },
  wordActions: { marginTop: 12 },
  primaryBtn: {
    backgroundColor: BRAND,
    borderRadius: 12,
    paddingVertical: 11,
    alignItems: "center",
  },
  primaryBtnText: { color: "#FFFFFF", fontSize: 15, fontWeight: "700" },
  wordMeta: { marginTop: 12, fontSize: 12, fontStyle: "italic", lineHeight: 17, color: "#777" },
  wordEmpty: { alignItems: "center", gap: 8, paddingVertical: 10 },
  wordEmptyText: { fontSize: 13, textAlign: "center", lineHeight: 19 },
  wordEmptySub: { fontSize: 12, textAlign: "center", color: "#777" },
  prayerText: { fontSize: 15, lineHeight: 24, fontStyle: "italic" },
  footerPad: { height: 24 },
});
