/**
 * Local cache of full-text readings (the missal body).
 *
 * This mirrors the pattern already used by `LiturgicalCache` for the calendar
 * header, but stores the complete `Reading` object returned by
 * `GET /api/readings/{date}?language=...` so the missal is usable offline.
 *
 * Keyed by date AND language so an English missal and a (future) Kiswahili
 * missal cache independently. TTL matches the liturgical cache (7 days).
 */
import AsyncStorage from "@react-native-async-storage/async-storage";

const CACHE_KEY_PREFIX = "readings_cache_";
const CACHE_EXPIRY_DAYS = 7;

export interface CachedReading {
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
  cached_at: string;
}

export class ReadingsCache {
  static async get(date: string, language: string): Promise<CachedReading | null> {
    try {
      const key = `${CACHE_KEY_PREFIX}${date}_${language}`;
      const raw = await AsyncStorage.getItem(key);
      if (!raw) return null;

      const data: CachedReading = JSON.parse(raw);
      const cachedDate = new Date(data.cached_at);
      const now = new Date();
      const daysSinceCache =
        (now.getTime() - cachedDate.getTime()) / (1000 * 60 * 60 * 24);

      if (daysSinceCache > CACHE_EXPIRY_DAYS) {
        await AsyncStorage.removeItem(key);
        return null;
      }
      return data;
    } catch (error) {
      console.error("Error reading reading cache:", error);
      return null;
    }
  }

  static async set(
    date: string,
    language: string,
    data: Omit<CachedReading, "cached_at">,
  ): Promise<void> {
    try {
      const key = `${CACHE_KEY_PREFIX}${date}_${language}`;
      await AsyncStorage.setItem(
        key,
        JSON.stringify({ ...data, cached_at: new Date().toISOString() }),
      );
    } catch (error) {
      console.error("Error writing reading cache:", error);
    }
  }

  static async clear(): Promise<void> {
    try {
      const keys = await AsyncStorage.getAllKeys();
      const cacheKeys = keys.filter((key) => key.startsWith(CACHE_KEY_PREFIX));
      if (cacheKeys.length > 0) {
        await AsyncStorage.multiRemove(cacheKeys);
      }
    } catch (error) {
      console.error("Error clearing reading cache:", error);
    }
  }

  static async size(): Promise<number> {
    try {
      const keys = await AsyncStorage.getAllKeys();
      return keys.filter((key) => key.startsWith(CACHE_KEY_PREFIX)).length;
    } catch (error) {
      console.error("Error getting reading cache size:", error);
      return 0;
    }
  }
}
