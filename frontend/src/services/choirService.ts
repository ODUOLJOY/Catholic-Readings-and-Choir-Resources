/**
 * The one place the app talks to the choir library.
 *
 * The browse screen used to call `api.get("/api/choir/")` inline and carry its
 * own `ChoirResource` interface. That meant the shape of a resource was declared
 * in two places that had already drifted -- the interface typed `duration` as a
 * `string` while the backend column is an `Integer` (seconds), so nothing caught
 * a bad value at the boundary. Everything choir now goes through here so the
 * response shape, the canonical category catalog and the failure classification
 * are defined exactly once.
 */

import { api } from "@/lib/api";
import { classifyRequestFailure, type RequestFailure } from "@/lib/requestFailure";
import { safeExternalUrl } from "@/lib/externalUrl";
import { readCachedCategories, writeCachedCategories } from "@/services/choirLibraryCache";
import { API_URL } from "@/config/api";
import {
  CHOIR_CATEGORIES,
  CHOIR_CATEGORY_SECTIONS,
  canonicaliseCategory,
} from "@/config/choirCategories";

export type ChoirFileKind = "audio" | "video" | "pdf" | "score" | "lyrics" | "other";

/** A choir library row as the API actually returns it. */
export interface ChoirResource {
  id: number;
  title: string;
  category: string;
  description: string | null;
  language: string | null;
  /** Seconds, for audio/video. `null` when unknown. */
  duration: number | null;
  file_type: string | null;
  file_url: string | null;
  file_size: number | null;
  composer: string | null;
  lyrics: string | null;
  alternative_title: string | null;
  author: string | null;
  arranger: string | null;
  voice_part: string | null;
  season: string | null;
  key_signature: string | null;
  tempo: string | null;
  /** Real counts from the database, never estimated on the client. */
  download_count: number | null;
  rating: number | null;
  parish_id: number | null;
  created_at: string | null;
  is_approved: boolean;
  is_published: boolean;
}

export interface ChoirCategorySection {
  title: string;
  categories: string[];
}

export interface ChoirCategoriesResponse {
  sections: ChoirCategorySection[];
  categories: string[];
  /** Canonical label -> visible resource count. All 27 keys are present. */
  counts: Record<string, number>;
  total: number;
}

export interface ChoirLibraryFilters {
  category?: string | null;
  /**
   * Several canonical categories in one request. Used by the "Prepare for Mass"
   * shelf, which spans the nine parts of the Mass ordinary. Nine separate
   * requests would each be ordered independently, so a part could look empty
   * while it actually has a resource.
   */
  categories?: string[];
  language?: string | null;
  season?: string | null;
  voicePart?: string | null;
  keySignature?: string | null;
  tempo?: string | null;
  composer?: string | null;
  query?: string | null;
  sort?: ChoirSort;
  limit?: number;
}

export type ChoirSort = "recent" | "popular" | "title";

export type ChoirFileKindResponse =
  | { kind: "ok"; data: ChoirResource }
  | { kind: "failure"; failure: RequestFailure };

export type ChoirCategoriesResult =
  | {
      kind: "ok";
      data: ChoirCategoriesResponse;
      /**
       * True when the payload came from the device snapshot rather than the
       * network, so the screen can say so instead of implying it is live.
       */
      offline?: boolean;
    }
  | { kind: "failure"; failure: RequestFailure };

/**
 * Turn the loose filter UI values into query parameters.
 *
 * Every value is an "All ..." sentinel in the UI, and sending one of those to the
 * API would filter on the literal string rather than mean "no filter". Only real
 * selections are sent.
 */
function buildParams(filters: ChoirLibraryFilters): Record<string, string> {
  const params: Record<string, string> = {};

  if (filters.query?.trim()) {
    params.query = filters.query.trim();
  }
  if (filters.category) {
    params.category = filters.category;
  }
  if (filters.categories?.length) {
    params.categories = filters.categories.join(",");
  }
  if (filters.language) {
    params.language = filters.language;
  }
  if (filters.season) {
    params.season = filters.season;
  }
  if (filters.voicePart) {
    params.voice_part = filters.voicePart;
  }
  if (filters.keySignature) {
    params.key_signature = filters.keySignature;
  }
  if (filters.tempo) {
    params.tempo = filters.tempo;
  }
  if (filters.composer?.trim()) {
    params.composer = filters.composer.trim();
  }
  if (filters.sort) {
    params.sort = filters.sort;
  }
  if (typeof filters.limit === "number") {
    params.limit = String(filters.limit);
  }

  return params;
}

function asOptionalString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function asOptionalNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/**
 * Normalise one row.
 *
 * The endpoint returns SQLAlchemy objects serialised by FastAPI, so every
 * nullable column arrives as `null` and nothing is guaranteed. Normalising here
 * means the screens can rely on `null` instead of `undefined` and on `duration`
 * being a number they can format directly.
 */
export function normaliseResource(raw: Record<string, unknown>): ChoirResource {
  return {
    id: Number(raw.id),
    title: asOptionalString(raw.title) ?? "",
    category: asOptionalString(raw.category) ?? "Others",
    description: asOptionalString(raw.description),
    language: asOptionalString(raw.language),
    duration: asOptionalNumber(raw.duration),
    file_type: asOptionalString(raw.file_type),
    file_url: asOptionalString(raw.file_url),
    file_size: asOptionalNumber(raw.file_size),
    composer: asOptionalString(raw.composer),
    lyrics: asOptionalString(raw.lyrics),
    alternative_title: asOptionalString(raw.alternative_title),
    author: asOptionalString(raw.author),
    arranger: asOptionalString(raw.arranger),
    voice_part: asOptionalString(raw.voice_part),
    season: asOptionalString(raw.season),
    key_signature: asOptionalString(raw.key_signature),
    tempo: asOptionalString(raw.tempo),
    download_count: asOptionalNumber(raw.download_count),
    rating: asOptionalNumber(raw.rating),
    parish_id: asOptionalNumber(raw.parish_id),
    created_at: asOptionalString(raw.created_at),
    is_approved: raw.is_approved === true,
    is_published: raw.is_published === true,
  };
}

/** Classify a file for iconography and preview affordances. */
export function fileKindOf(resource: Pick<ChoirResource, "file_type" | "title">): ChoirFileKind {
  const type = resource.file_type?.toLowerCase() ?? "";
  const title = resource.title.toLowerCase();

  if (type.includes("audio") || /\b(mp3|m4a|wav|aac|flac|ogg)\b/.test(type)) {
    return "audio";
  }
  if (type.includes("video") || /\b(mp4|mov|webm|mkv)\b/.test(type)) {
    return "video";
  }
  if (type.includes("sheet") || type.includes("score")) {
    return "score";
  }
  if (type.includes("lyric") || title.includes("lyric")) {
    return "lyrics";
  }
  if (type.includes("pdf")) {
    return "pdf";
  }
  return "other";
}

/**
 * The URL the player and the "open" action use.
 *
 * `file_url` is a value this client does not control, so it goes through
 * `safeExternalUrl`, which refuses any scheme other than http(s). A `file:`,
 * `data:` or app deep link stored in the database must never be handed to the
 * OS handler. Returns `null` when there is nothing usable to open.
 */
export function resourceFileUrl(resource: Pick<ChoirResource, "file_url">): string | null {
  return safeExternalUrl(resource.file_url, API_URL);
}

/** Seconds as `m:ss`, or `null` when the duration is unknown. */
export function formatDuration(seconds: number | null): string | null {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) {
    return null;
  }
  const whole = Math.floor(seconds);
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const secs = whole % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }
  return `${minutes}:${String(secs).padStart(2, "0")}`;
}

const NOT_FOUND = "That choir resource is not available.";

export async function fetchCategories(): Promise<ChoirCategoriesResult> {
  try {
    const response = await api.get("/api/choir/categories");
    const raw = response.data as Partial<ChoirCategoriesResponse>;

    const sections: ChoirCategorySection[] = Array.isArray(raw.sections)
      ? raw.sections.map((section) => ({
          title: String(section.title ?? ""),
          categories: Array.isArray(section.categories)
            ? section.categories.map(String)
            : [],
        }))
      : [];

    // Fall back to the compiled-in catalog if the server omitted sections, so
    // the page still renders the required 27 in order rather than nothing.
    const categories = Array.isArray(raw.categories) && raw.categories.length
      ? raw.categories.map(String)
      : [...CHOIR_CATEGORIES];

    const counts: Record<string, number> = {};
    for (const label of categories) {
      const value = (raw.counts as Record<string, unknown> | undefined)?.[label];
      counts[label] = typeof value === "number" && Number.isFinite(value) && value > 0 ? value : 0;
    }

    const total = typeof raw.total === "number" ? raw.total : Object.values(counts).reduce((a, b) => a + b, 0);

    const data = {
      sections: sections.length
        ? sections
        : CHOIR_CATEGORY_SECTIONS.map((section) => ({
            title: section.title,
            categories: [...section.categories],
          })),
      categories,
      counts,
      total,
    };

    // Snapshot for offline browsing. Fire-and-forget: never block the response.
    void writeCachedCategories(data);

    return { kind: "ok", data };
  } catch (error) {
    const failure = classifyRequestFailure(error, {
      fallbackNotFound: "The choir library categories are unavailable.",
      fallbackMessage: "Could not load the choir library categories. Check your connection and try again.",
    });

    // A lost connection falls back to the last stored taxonomy so the 27
    // categories stay browsable offline. `server`, `unauthorized`, `forbidden`
    // and `not-found` deliberately do not: those are real answers about this
    // account and request rather than a missing connection, and serving a
    // stale snapshot in their place would hide a problem the member needs to
    // see. A 500 is included in the fallback because a transient restart
    // should not empty the whole library.
    if (failure.kind === "network" || failure.kind === "server") {
      const cached = await readCachedCategories();
      if (cached) {
        return {
          kind: "ok",
          data: {
            sections: cached.sections,
            categories: cached.categories,
            counts: cached.counts,
            total: cached.total,
          },
          offline: true,
        };
      }
    }

    return { kind: "failure", failure };
  }
}

/**
 * Resources matching the filters.
 *
 * A failure is returned rather than thrown so a browse screen can render the
 * library shell with an inline retry instead of discarding the whole page.
 */
export async function fetchResources(
  filters: ChoirLibraryFilters = {},
): Promise<{ kind: "ok"; data: ChoirResource[] } | { kind: "failure"; failure: RequestFailure }> {
  try {
    const response = await api.get("/api/choir/", { params: buildParams(filters) });
    const payload = Array.isArray(response.data)
      ? response.data
      : Array.isArray(response.data?.items)
        ? response.data.items
        : [];

    return {
      kind: "ok",
      data: (payload as Record<string, unknown>[]).map(normaliseResource),
    };
  } catch (error) {
    return {
      kind: "failure",
      failure: classifyRequestFailure(error, {
        fallbackNotFound: NOT_FOUND,
        fallbackMessage: "Could not reach the choir library. Check your connection and try again.",
      }),
    };
  }
}

export async function fetchResource(id: number): Promise<ChoirFileKindResponse> {
  try {
    const response = await api.get(`/api/choir/${id}`);
    return { kind: "ok", data: normaliseResource(response.data as Record<string, unknown>) };
  } catch (error) {
    return {
      kind: "failure",
      failure: classifyRequestFailure(error, { fallbackNotFound: NOT_FOUND }),
    };
  }
}

/**
 * A curated "Prepare for Mass" group.
 *
 * The Mass ordinary is always the same shape, so the recommended order is a
 * property of the Catholic rite rather than an editorial opinion, and it is
 * keyed off the canonical category labels. Nothing here invents a resource: an
 * absent category simply contributes no rows.
 */
export const MASS_ORDINARY_ORDER = [
  "Entrance",
  "Kyrie & Gloria",
  "Responsorial Psalm",
  "Sadaka",
  "Offertory",
  "Sanctus",
  "Agnus Dei",
  "Communion",
  "Exit",
] as const;

/**
 * Order a pool into the Mass ordinary sequence, keeping only canonical labels
 * and dropping anything the library does not have.
 */
export function orderForMass(resources: ChoirResource[]): ChoirResource[] {
  const byCategory = new Map<string, ChoirResource>();
  for (const resource of resources) {
    const canonical = canonicaliseCategory(resource.category);
    if (canonical && !byCategory.has(canonical)) {
      byCategory.set(canonical, resource);
    }
  }
  return MASS_ORDINARY_ORDER.map((label) => byCategory.get(label)).filter(
    (resource): resource is ChoirResource => Boolean(resource),
  );
}