/**
 * Today's liturgical context for the choir library.
 *
 * The browse screen used to open with a hard-coded "Catholic Mass Songs, Hymns &
 * Choir Resources" subtitle regardless of the date, which meant it could never
 * tell a choir what to prepare for *this* Sunday. This hook asks the existing
 * liturgy service instead, so the celebration name, season, week and colour on
 * the page are the same values the readings screen shows for the same day.
 *
 * Two existing pieces are reused rather than replaced:
 *   - `LiturgicalCache` for the offline/offline-first read path.
 *   - `GET /api/v1/liturgy/today`, which is already the app's public endpoint.
 *
 * Nothing here invents a season. When the service is unreachable the hook
 * reports `null` and the screen renders without the context block rather than
 * guessing at Easter in April.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import { LiturgicalCache, type CachedLiturgicalDay } from "@/services/liturgicalCache";
import { LITURGY_REGION } from "@/services/readingsService";
import { canonicaliseCategory } from "@/config/choirCategories";

export interface LiturgicalToday {
  date: string;
  celebration: string | null;
  rank: string | null;
  season: string | null;
  week: number | null;
  /** The liturgical colour exactly as the service spells it, e.g. "green". */
  colour: string | null;
  sundayCycle: string | null;
  weekdayCycle: string | null;
  /**
   * The matching canonical choir season category, when the service's season name
   * is one of the library's season categories. `null` otherwise -- the caller
   * must not substitute a guess.
   */
  seasonCategory: string | null;
  fromCache: boolean;
}

export type LiturgicalTodayState =
  | { status: "loading"; value: null }
  | { status: "ready"; value: LiturgicalToday }
  | { status: "unavailable"; value: null };

function localDate(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

function toToday(day: CachedLiturgicalDay, fromCache: boolean): LiturgicalToday {
  const season = day.liturgical?.season ?? null;
  return {
    date: day.date,
    celebration: day.celebration?.name ?? null,
    rank: day.celebration?.rank ?? null,
    season,
    week: day.liturgical?.week ?? null,
    colour: day.liturgical?.colour ?? null,
    sundayCycle: day.liturgical?.sunday_cycle ?? null,
    weekdayCycle: day.liturgical?.weekday_cycle ?? null,
    // Only the seven canonical season categories can be suggested. A calendar
    // engine that names a season the library does not carry yields `null`.
    seasonCategory: season ? canonicaliseCategory(season) : null,
    fromCache,
  };
}

async function fetchToday(): Promise<CachedLiturgicalDay> {
  const response = await api.get("/api/v1/liturgy/today", {
    params: { region: LITURGY_REGION },
  });
  const day = response.data as CachedLiturgicalDay;
  // Populate the shared cache so the readings screen benefits too. A cache write
  // failure must not turn a successful fetch into an error.
  try {
    await LiturgicalCache.set(day.date, day.region ?? LITURGY_REGION, day);
  } catch {
    // ignored on purpose: the value in hand is already correct.
  }
  return day;
}

export function useLiturgicalToday(): LiturgicalTodayState & { reload: () => void } {
  const [state, setState] = useState<LiturgicalTodayState>({ status: "loading", value: null });
  const [attempt, setAttempt] = useState(0);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);

  useEffect(() => {
    let cancelled = false;
    const today = localDate();

    async function load() {
      // 1) Cache first: renders immediately and works offline.
      const cached = await LiturgicalCache.get(today, LITURGY_REGION).catch(() => null);
      if (cached && !cancelled) {
        setState({ status: "ready", value: toToday(cached, true) });
      } else if (!cancelled) {
        setState({ status: "loading", value: null });
      }

      // 2) Then refresh from the service.
      try {
        const fresh = await fetchToday();
        if (!cancelled) {
          setState({ status: "ready", value: toToday(fresh, false) });
        }
      } catch {
        // A failure only matters when there is nothing to show. With a cached day
        // already on screen the member keeps a usable (clearly marked) context.
        if (!cancelled) {
          setState((current) =>
            current.status === "ready"
              ? current
              : { status: "unavailable", value: null },
          );
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  // Memoised deliberately. A fresh object literal on every render would give the
  // browse screen a new dependency identity each pass, and its effect that loads
  // the season shelf would re-fire forever.
  return useMemo(() => ({ ...state, reload }), [state, reload]);
}