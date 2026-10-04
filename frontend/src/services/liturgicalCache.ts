import AsyncStorage from "@react-native-async-storage/async-storage";

const CACHE_KEY_PREFIX = "liturgical_cache_";
const CACHE_EXPIRY_DAYS = 7; // Cache for 7 days

export interface CachedLiturgicalDay {
  date: string;
  region: string;
  celebration: {
    name: string;
    rank: string;
  };
  liturgical: {
    season: string;
    week: number | null;
    colour: string;
    sunday_cycle: string;
    weekday_cycle: string;
  };
  readings: Array<{
    type: string;
    book: string;
    display_reference: string;
    is_alternative: boolean;
    is_optional: boolean;
    is_primary: boolean;
  }>;
  available_reading_sets: any[];
  source: {
    name: string | null;
    region: string;
  } | null;
  verification_status: string;
  cached_at: string;
}

export class LiturgicalCache {
  /**
   * Get cached liturgical data for a date
   */
  static async get(date: string, region: string = "KE"): Promise<CachedLiturgicalDay | null> {
    try {
      const key = `${CACHE_KEY_PREFIX}${date}_${region}`;
      const cached = await AsyncStorage.getItem(key);
      
      if (!cached) {
        return null;
      }
      
      const data: CachedLiturgicalDay = JSON.parse(cached);
      
      // Check if cache is expired
      const cachedDate = new Date(data.cached_at);
      const now = new Date();
      const daysSinceCache = (now.getTime() - cachedDate.getTime()) / (1000 * 60 * 60 * 24);
      
      if (daysSinceCache > CACHE_EXPIRY_DAYS) {
        // Cache expired, remove it
        await AsyncStorage.removeItem(key);
        return null;
      }
      
      return data;
    } catch (error) {
      console.error("Error reading from cache:", error);
      return null;
    }
  }

  /**
   * Cache liturgical data for a date
   */
  static async set(date: string, region: string, data: Omit<CachedLiturgicalDay, "cached_at">): Promise<void> {
    try {
      const key = `${CACHE_KEY_PREFIX}${date}_${region}`;
      const cacheData: CachedLiturgicalDay = {
        ...data,
        cached_at: new Date().toISOString(),
      };
      await AsyncStorage.setItem(key, JSON.stringify(cacheData));
    } catch (error) {
      console.error("Error writing to cache:", error);
    }
  }

  /**
   * Clear all cached liturgical data
   */
  static async clear(): Promise<void> {
    try {
      const keys = await AsyncStorage.getAllKeys();
      const cacheKeys = keys.filter(key => key.startsWith(CACHE_KEY_PREFIX));
      if (cacheKeys.length > 0) {
        await AsyncStorage.multiRemove(cacheKeys);
      }
    } catch (error) {
      console.error("Error clearing cache:", error);
    }
  }

  /**
   * Get cache size (number of cached days)
   */
  static async size(): Promise<number> {
    try {
      const keys = await AsyncStorage.getAllKeys();
      return keys.filter(key => key.startsWith(CACHE_KEY_PREFIX)).length;
    } catch (error) {
      console.error("Error getting cache size:", error);
      return 0;
    }
  }
}
