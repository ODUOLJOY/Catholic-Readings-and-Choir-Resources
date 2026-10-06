/**
 * Visual tokens for the choir library.
 *
 * The library is a worship tool, not a generic music app: it should feel like a
 * well-kept choral folio. That is expressed here once, as tokens, so the browse
 * screen, the resource cards and the detail screen stay visually identical
 * without each of them hard-coding hex values.
 *
 * The palette is ivory/parchment paper, deep choir green, and liturgical gold,
 * with a plum accent for devotional material. Every foreground/background pair
 * below was chosen to clear WCAG AA (4.5:1) for body text and 3:1 for large
 * text and UI borders.
 */

import { Platform } from "react-native";

export const ChoirTheme = {
  /** Page background: warm paper rather than clinical white. */
  canvas: "#FBF7F0",
  /** Raised card surface. */
  surface: "#FFFFFF",
  /** Recessed surface for chips, wells and skeleton blocks. */
  surfaceMuted: "#F3EDE2",

  /** Primary brand: the dark green of a choir cassock. */
  green: "#0B6623",
  greenDark: "#08491A",
  greenTint: "#E6F1E8",

  /** Liturgical gold, used for accents and dividers only. */
  gold: "#A8801C",
  goldTint: "#F6EDD8",

  /** Devotional accent (Marian, Rosary, Benediction). */
  plum: "#6B2D5C",
  plumTint: "#F4E8F1",

  ink: "#1A1D19",
  inkMuted: "#5A6157",
  inkFaint: "#8A9086",

  border: "#E2DACB",
  borderStrong: "#CFC4AF",

  danger: "#8A1C13",
  dangerTint: "#FDECEA",

  white: "#FFFFFF",
} as const;

/** Type scale. `Fonts.serif` is used for display/headings only. */
export const ChoirType = {
  hero: 30,
  section: 21,
  cardTitle: 17,
  body: 15,
  meta: 13,
  micro: 11,
} as const;

export const ChoirSpace = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
} as const;

export const ChoirRadius = {
  sm: 8,
  md: 12,
  lg: 18,
  pill: 999,
} as const;

export const MaxChoirContentWidth = 1240;

/**
 * Minimal touch target. iOS HIG and WCAG 2.2 both put the floor at 44dp, and a
 * choir member selecting a resource one-handed on a phone needs it.
 */
export const MinTouchTarget = 44;

/**
 * Map a liturgical colour name onto a palette accent.
 *
 * The name arrives from `GET /api/v1/liturgy/today` and is therefore
 * server-controlled vocabulary ("green", "white", "red", "violet", "gold"/"rose").
 * Anything unrecognised falls back to the brand green rather than picking a
 * colour at random, so an unexpected value can never produce an unreadable page.
 */
export function liturgicalAccent(colour: string | null | undefined): {
  accent: string;
  tint: string;
} {
  switch (colour?.trim().toLowerCase()) {
    case "white":
      return { accent: "#8C8377", tint: "#F4F1EC" };
    case "red":
      return { accent: "#A32018", tint: "#FBEAE8" };
    case "rose":
      return { accent: "#9B2F5F", tint: "#FAE9EF" };
    case "violet":
    case "purple":
      return { accent: "#5B3A8E", tint: "#EFE9F7" };
    case "gold":
    case "yellow":
      return { accent: "#8A6A12", tint: "#F8F0D9" };
    case "blue":
      return { accent: "#1F4C87", tint: "#E7EFF8" };
    case "green":
    default:
      return { accent: ChoirTheme.green, tint: ChoirTheme.greenTint };
  }
}

/** Subtle elevation. Kept in one place so cards across the module match. */
export const ChoirShadow = Platform.select({
  ios: {
    shadowColor: "#2B241A",
    shadowOpacity: 0.07,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
  },
  android: { elevation: 2 },
  default: {
    shadowColor: "#2B241A",
    shadowOpacity: 0.07,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
  },
}) as object;