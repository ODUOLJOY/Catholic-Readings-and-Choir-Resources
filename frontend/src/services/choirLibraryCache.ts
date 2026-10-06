/**
 * Offline snapshot of the choir library *taxonomy*.
 *
 * Scope is deliberate and narrow. Only the category names and their public
 * counts are cached -- never a resource list. Resource visibility is decided
 * per request (`approved`/`published` plus parish membership), so replaying a
 * stored list offline could show a member something their account is no longer
 * entitled to see. Individual files are handled separately by `offlineStore`,
 * where the member saved them on purpose.
 */

import AsyncStorage from "@react-native-async-storage/async-storage";

import { CHOIR_CATEGORIES, CHOIR_CATEGORY_SECTIONS } from "@/config/choirCategories";

const KEY = "CHOIR_LIBRARY_CATEGORIES";
const MAX_AGE_MS = 1000 * 60 * 60 * 24 * 7;

export interface CachedChoirCategories {
  sections: { title: string; categories: string[] }[];
  categories: string[];
  counts: Record<string, number>;
  total: number;
  /** Epoch ms of the snapshot. */
  cachedAt: number;
}

export async function writeCachedCategories(
  value: Omit<CachedChoirCategories, "cachedAt">,
): Promise<void> {
  try {
    const payload: CachedChoirCategories = { ...value, cachedAt: Date.now() };
    await AsyncStorage.setItem(KEY, JSON.stringify(payload));
  } catch {
    // A snapshot is an optimisation. Failing to write one must never turn a
    // successful load into an error.
  }
}

/**
 * The stored taxonomy, or null when absent or stale.
 *
 * Staleness is checked here rather than at render time so the caller gets a
 * single decision instead of having to reason about ages.
 */
export async function readCachedCategories(): Promise<CachedChoirCategories | null> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<CachedChoirCategories>;
    if (typeof parsed.cachedAt !== "number" || Date.now() - parsed.cachedAt > MAX_AGE_MS) {
      return null;
    }
    const categories =
      Array.isArray(parsed.categories) && parsed.categories.length
        ? parsed.categories.map(String)
        : [...CHOIR_CATEGORIES];
    const counts: Record<string, number> = {};
    for (const label of categories) {
      const value = parsed.counts?.[label];
      counts[label] = typeof value === "number" && Number.isFinite(value) && value > 0 ? value : 0;
    }
    return {
      sections: Array.isArray(parsed.sections) && parsed.sections.length
        ? parsed.sections
        : CHOIR_CATEGORY_SECTIONS.map((section) => ({
            title: section.title,
            categories: [...section.categories],
          })),
      categories,
      counts,
      total: typeof parsed.total === "number" ? parsed.total : Object.values(counts).reduce((a, b) => a + b, 0),
      cachedAt: parsed.cachedAt,
    };
  } catch {
    return null;
  }
}