/**
 * Single façade for the Reading screen's data.
 *
 * The authoritative backend exposes two endpoints this screen needs:
 *
 *   - `GET /api/v1/liturgy/date/{date}?region=KE`  → the liturgical calendar
 *     header (celebration, rank, season, week, colour, A/B/C + I/II cycles,
 *     source, verification status). Public, region-based.
 *
 *   - `GET /api/readings/{date}?language=...`        → the full published
 *     Scripture text for a date (first reading, responsorial psalm + response,
 *     optional second reading, gospel acclamation, gospel, reflection,
 *     prayer, source). Public; defaults to English; returns 404 when a
 *     translation does not exist (e.g. Kiswahili).
 *
 * This module does NOT invent Scripture or liturgical metadata. It only maps
 * the real backend shapes into the typed `MissalReading` the UI renders, and
 * owns the offline contract: cache-first, network on miss, cache fallback
 * when the network is unavailable.
 */
import AsyncStorage from "@react-native-async-storage/async-storage";

import { api } from "@/lib/api";
import { LiturgicalCache } from "@/services/liturgicalCache";
import { ReadingsCache } from "@/services/readingsCache";

export const LITURGY_REGION = "KE";
export const LANGUAGES = ["English", "Kiswahili"] as const;
export type ReadingLanguage = (typeof LANGUAGES)[number];
export const DEFAULT_LANGUAGE: ReadingLanguage = "English";
export const LANGUAGE_STORAGE_KEY = "reading_language";

export type ReadingSectionType =
  | "first_reading"
  | "psalm"
  | "second_reading"
  | "gospel";

export interface ReadingSection {
  type: ReadingSectionType;
  /** Human label, e.g. "First Reading", "Responsorial Psalm". */
  title: string;
  reference?: string;
  /** Gospel intro formula generated from the gospel reference. */
  introduction?: string;
  /** Responsorial psalm response, rendered with the "R/" prefix. */
  response?: string;
  text: string;
  /** False when the authoritative source has not provided this text yet. */
  available: boolean;
}

export interface LiturgicalHeader {
  date: string;
  celebration: string | null;
  rank: string | null;
  season: string | null;
  week: number | null;
  liturgicalColor: string | null;
  sundayCycle: string | null; // A / B / C
  weekdayCycle: string | null; // I / II
  source: string | null;
  verificationStatus: string;
}

export interface MissalReading {
  id: number | null;
  date: string;
  language: ReadingLanguage;
  header: LiturgicalHeader;
  sections: ReadingSection[];
  reflection: string | null;
  prayer: string | null;
  gospelAcclamation: string | null;
  source: string | null;
}

export interface MissalLoadResult {
  data: MissalReading;
  fromCache: boolean;
  offline: boolean;
  /** True when the authoritative reading text for this date/language is absent. */
  notFound: boolean;
  /**
   * When the member asked for Kiswahili but no Kiswahili text exists, the
   * English missal for the same date is offered as a read-only fallback so the
   * page is never empty. `null` when unavailable.
   */
  englishFallback?: MissalReading | null;
}

// --- Authoritative backend shapes (verified against route output) ---

interface RawLiturgicalDay {
  date: string;
  region: string;
  celebration: { name: string; rank: string } | null;
  liturgical: {
    season: string;
    week: number | null;
    colour: string;
    sunday_cycle: string;
    weekday_cycle: string;
  };
  readings: {
    type: string;
    book: string;
    display_reference: string;
    is_alternative: boolean;
    is_optional: boolean;
    is_primary: boolean;
    sequence?: number;
  }[];
  available_reading_sets: unknown[];
  source: { name: string | null; region: string } | null;
  verification_status: string;
}

interface RawReading {
  id: number;
  reading_date: string;
  language: string;
  liturgical_year: string;
  liturgical_season: string;
  liturgical_color: string;
  feast: string | null;
  saint_of_day: string | null;
  is_holy_day: boolean;
  first_reading_reference: string;
  first_reading: string;
  responsorial_psalm_reference: string | null;
  responsorial_psalm: string | null;
  responsorial_response: string | null;
  second_reading_reference: string | null;
  second_reading: string | null;
  gospel_acclamation: string | null;
  gospel_reference: string;
  gospel: string;
  reflection: string | null;
  prayer: string | null;
  source: string | null;
  published: boolean;
  approved: boolean;
}

interface AxiosLikeError {
  response?: { status?: number };
}

function isAxiosErrorWithStatus(error: unknown): number | undefined {
  const status = (error as AxiosLikeError | null)?.response?.status;
  return typeof status === "number" ? status : undefined;
}

type LiturgicalCacheSetArg = Parameters<typeof LiturgicalCache.set>[2];
type ReadingsCacheSetArg = Parameters<typeof ReadingsCache.set>[2];

// ---------------------------------------------------------------------------
// Language preference (persisted so EN/Kiswahili survives a reload).
// ---------------------------------------------------------------------------

export async function setLanguage(language: ReadingLanguage): Promise<void> {
  await AsyncStorage.setItem(LANGUAGE_STORAGE_KEY, language);
}

export async function getLanguage(): Promise<ReadingLanguage> {
  const stored = await AsyncStorage.getItem(LANGUAGE_STORAGE_KEY);
  return stored === "Kiswahili" ? "Kiswahili" : DEFAULT_LANGUAGE;
}

// ---------------------------------------------------------------------------
// Network fetchers (cache-aware). Each honours cache-first, caches on success.
// ---------------------------------------------------------------------------

async function fetchLiturgicalDay(
  dateStr: string,
): Promise<RawLiturgicalDay | null> {
  const cached = await LiturgicalCache.get(dateStr, LITURGY_REGION);
  if (cached) return cached as unknown as RawLiturgicalDay;

  const res = await api.get(`/api/v1/liturgy/date/${dateStr}`, {
    params: { region: LITURGY_REGION },
  });
  const data = res.data as RawLiturgicalDay;
  await LiturgicalCache.set(
    dateStr,
    LITURGY_REGION,
    data as unknown as LiturgicalCacheSetArg,
  );
  return data;
}

async function fetchLiturgicalDayQuiet(
  dateStr: string,
): Promise<RawLiturgicalDay | null> {
  try {
    return await fetchLiturgicalDay(dateStr);
  } catch {
    return null;
  }
}

async function fetchReading(
  dateStr: string,
  language: ReadingLanguage,
): Promise<RawReading> {
  const cached = await ReadingsCache.get(dateStr, language);
  if (cached) return cached as unknown as RawReading;

  const res = await api.get(`/api/readings/${dateStr}`, {
    params: { language },
  });
  const data = res.data as RawReading;
  await ReadingsCache.set(
    dateStr,
    language,
    data as unknown as ReadingsCacheSetArg,
  );
  return data;
}

export async function getReadingById(
  id: number,
  language: ReadingLanguage,
): Promise<RawReading> {
  const res = await api.get(`/api/readings/id/${id}`, { params: { language } });
  const data = res.data as RawReading;
  // Cache by the reading's own date so a later date-based open is instant.
  void ReadingsCache.set(
    data.reading_date,
    language,
    data as unknown as ReadingsCacheSetArg,
  );
  return data;
}

// ---------------------------------------------------------------------------
// Public API consumed by the screen.
// ---------------------------------------------------------------------------

/** The missal for the requested date/language, with an offline/cache policy. */
export async function getMissalByDate(
  dateStr: string,
  language: ReadingLanguage,
): Promise<MissalLoadResult> {
  const cachedReading = await ReadingsCache.get(dateStr, language);
  const cachedLiturgy = await LiturgicalCache.get(dateStr, LITURGY_REGION);

  // 1) Cache-first: serve what we have immediately (still online for now).
  if (cachedReading) {
    const header = cachedLiturgy ?? (await fetchLiturgicalDayQuiet(dateStr));
    return {
      data: mergeMissal(dateStr, language, header, cachedReading),
      fromCache: true,
      offline: false,
      notFound: false,
    };
  }

  // 2) Network.
  try {
    const [lit, reading] = await Promise.all([
      fetchLiturgicalDay(dateStr),
      fetchReading(dateStr, language),
    ]);
    return {
      data: mergeMissal(dateStr, language, lit, reading),
      fromCache: false,
      offline: false,
      notFound: false,
    };
  } catch (error) {
    const status = isAxiosErrorWithStatus(error);

    // 404 on the reading text is expected for untranslated dates (Kiswahili).
    // The calendar header may still be available, so we render it with the
    // proper references and an "unavailable" notice instead of failing.
    if (status === 404) {
      const header = cachedLiturgy ?? (await fetchLiturgicalDayQuiet(dateStr));

      let englishFallback: MissalReading | null = null;
      if (language === "Kiswahili") {
        // The English text is authoritative and may still exist even when the
        // selected language does not. Offer it as a read-only fallback so the
        // page is never empty -- never fabricate Swahili text.
        try {
          const enReading = await fetchReading(dateStr, "English");
          englishFallback = mergeMissal(dateStr, "English", header, enReading);
        } catch {
          englishFallback = null;
        }
      }

      return {
        data: mergeMissal(dateStr, language, header, null, header),
        fromCache: false,
        offline: false,
        notFound: true,
        englishFallback,
      };
    }

    // 3) Network failure: fall back to any cached reading (offline mode).
    if (cachedReading) {
      return {
        data: mergeMissal(dateStr, language, cachedLiturgy, cachedReading),
        fromCache: true,
        offline: true,
        notFound: false,
      };
    }

    throw error;
  }
}

/** Force a network refresh, used by pull-to-refresh. */
export async function refreshMissal(
  dateStr: string,
  language: ReadingLanguage,
): Promise<MissalLoadResult> {
  const [litRes, readRes] = await Promise.all([
    api.get(`/api/v1/liturgy/date/${dateStr}`, {
      params: { region: LITURGY_REGION },
    }),
    api.get(`/api/readings/${dateStr}`, { params: { language } }),
  ]);
  const lit = litRes.data as RawLiturgicalDay;
  const reading = readRes.data as RawReading | undefined;
  void LiturgicalCache.set(
    dateStr,
    LITURGY_REGION,
    lit as unknown as LiturgicalCacheSetArg,
  );
  if (reading) {
    void ReadingsCache.set(
      dateStr,
      language,
      reading as unknown as ReadingsCacheSetArg,
    );
    return {
      data: mergeMissal(dateStr, language, lit, reading),
      fromCache: false,
      offline: false,
      notFound: false,
    };
  }
  return {
    data: mergeMissal(dateStr, language, lit, null, lit),
    fromCache: false,
    offline: false,
    notFound: true,
  };
}

// ---------------------------------------------------------------------------
// Merge the two authoritative payloads into the UI model.
// ---------------------------------------------------------------------------

const GENERIC_CELEBRATIONS = new Set(["Weekday", "Feria", "Ferias", "Sunday"]);

/**
 * Ordinal for "27th Week in Ordinary Time".
 * Exported for the header.
 */
export function ordinal(n: number): string {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return `${n}${s[(v - 20) % 10] || s[v] || s[0]}`;
}

/** Book name extracted from a scripture reference like "Luke 10:25-33". */
function bookFromReference(reference: string): string | null {
  const match = reference.trim().match(/^([^\d\s]+(?:\s+[^\d\s]+)*?)\s+\d/);
  return match ? match[1] : reference.trim() || null;
}

/**
 * The Gospel intro is the fixed Roman Missal formula, derived from the
 * gospel reference. This is liturgical wording (not Scripture), so deriving the
 * book from the reference is not fabricating a reading.
 */
function gospelIntroduction(reference: string): string {
  const book = bookFromReference(reference) ?? "the Gospel";
  return `A reading from the Holy Gospel according to ${book}`;
}

function sectionTitle(type: ReadingSectionType): string {
  switch (type) {
    case "first_reading":
      return "First Reading";
    case "psalm":
      return "Responsorial Psalm";
    case "second_reading":
      return "Second Reading";
    case "gospel":
      return "Gospel";
  }
}

function buildSections(
  reading: RawReading | null,
  liturgy: RawLiturgicalDay | null | undefined,
): ReadingSection[] {
  if (reading) {
    const sections: ReadingSection[] = [];
    sections.push({
      type: "first_reading",
      title: sectionTitle("first_reading"),
      reference: reading.first_reading_reference || undefined,
      text: reading.first_reading ?? "",
      available: Boolean(reading.first_reading?.trim()),
    });

    if (reading.responsorial_psalm) {
      sections.push({
        type: "psalm",
        title: sectionTitle("psalm"),
        reference: reading.responsorial_psalm_reference || undefined,
        response: reading.responsorial_response || undefined,
        text: reading.responsorial_psalm ?? "",
        available: Boolean(reading.responsorial_psalm?.trim()),
      });
    }

    if (reading.second_reading) {
      sections.push({
        type: "second_reading",
        title: sectionTitle("second_reading"),
        reference: reading.second_reading_reference || undefined,
        text: reading.second_reading ?? "",
        available: true,
      });
    }

    sections.push({
      type: "gospel",
      title: sectionTitle("gospel"),
      reference: reading.gospel_reference || undefined,
      introduction: gospelIntroduction(reading.gospel_reference),
      text: reading.gospel ?? "",
      available: Boolean(reading.gospel?.trim()),
    });
    return sections;
  }

  // Reading text unavailable -- fall back to calendar references if present.
  if (liturgy && liturgy.readings?.length > 0) {
    return liturgy.readings
      .slice()
      .sort((a, b) => (a.sequence ?? 0) - (b.sequence ?? 0))
      .map((ref): ReadingSection => {
        const type = normalizeRefType(ref.type);
        return {
          type,
          title: refTypeLabel(ref.type),
          reference: ref.display_reference || undefined,
          text: "",
          available: false,
        };
      });
  }

  return [];
}

const REF_TYPE_LABEL: Record<string, string> = {
  FIRST_READING: "First Reading",
  RESPONSORIAL_PSALM: "Responsorial Psalm",
  SECOND_READING: "Second Reading",
  GOSPEL_ACCLAMATION: "Gospel Acclamation",
  GOSPEL: "Gospel",
};

function refTypeLabel(type: string): string {
  return REF_TYPE_LABEL[type] ?? type;
}

function normalizeRefType(type: string): ReadingSectionType {
  const t = type.toLowerCase();
  if (t.includes("first")) return "first_reading";
  if (t.includes("psalm")) return "psalm";
  if (t.includes("second")) return "second_reading";
  return "gospel";
}

function mergeMissal(
  dateStr: string,
  language: ReadingLanguage,
  liturgy: RawLiturgicalDay | null,
  reading: RawReading | null,
  fallbackLiturgy?: RawLiturgicalDay | null,
): MissalReading {
  const headerLiturgy = liturgy ?? fallbackLiturgy ?? null;

  const celebration =
    headerLiturgy?.celebration?.name &&
    !GENERIC_CELEBRATIONS.has(headerLiturgy.celebration.name)
      ? headerLiturgy.celebration.name
      : reading?.feast ?? null;

  const season =
    reading?.liturgical_season ??
    headerLiturgy?.liturgical?.season ??
    null;
  const color =
    reading?.liturgical_color ??
    headerLiturgy?.liturgical?.colour ??
    null;
  const sundayCycle =
    reading?.liturgical_year ??
    headerLiturgy?.liturgical?.sunday_cycle ??
    null;

  const header: LiturgicalHeader = {
    date: dateStr,
    celebration,
    rank: headerLiturgy?.celebration?.rank ?? null,
    season,
    week: headerLiturgy?.liturgical?.week ?? null,
    liturgicalColor: color,
    sundayCycle,
    weekdayCycle: headerLiturgy?.liturgical?.weekday_cycle ?? null,
    source: reading?.source ?? headerLiturgy?.source?.name ?? null,
    verificationStatus: headerLiturgy?.verification_status ?? "unverified",
  };

  return {
    id: reading?.id ?? null,
    date: dateStr,
    language,
    header,
    sections: buildSections(reading, headerLiturgy),
    reflection: reading?.reflection ?? null,
    prayer: reading?.prayer ?? null,
    gospelAcclamation: reading?.gospel_acclamation ?? null,
    source: reading?.source ?? headerLiturgy?.source?.name ?? null,
  };
}
