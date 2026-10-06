/**
 * One resource in the choir library.
 *
 * Used by every shelf on the browse screen (featured, prepare-for-Mass, loved,
 * recent, practice, search results) so a resource looks identical wherever it
 * appears. The card is a single tap target that opens the detail screen; the
 * bookmark and the play affordance are separate nested controls.
 */

import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";

import {
  ChoirRadius,
  ChoirShadow,
  ChoirSpace,
  ChoirTheme,
  ChoirType,
  MinTouchTarget,
} from "@/constants/choirTheme";
import {
  fileKindOf,
  formatDuration,
  resourceFileUrl,
  type ChoirResource,
} from "@/services/choirService";

type IconName = React.ComponentProps<typeof Ionicons>["name"];

const KIND_ICON: Record<string, IconName> = {
  audio: "musical-notes",
  video: "videocam",
  pdf: "document-text",
  score: "musical-note",
  lyrics: "chatbox-ellipses",
  other: "document-outline",
};

const KIND_LABEL: Record<string, string> = {
  audio: "Audio",
  video: "Video",
  pdf: "PDF",
  score: "Score",
  lyrics: "Lyrics",
  other: "File",
};

function useAccentTone(kind: string): { background: string; foreground: string } {
  switch (kind) {
    case "audio":
      return { background: ChoirTheme.greenTint, foreground: ChoirTheme.green };
    case "video":
      return { background: "#E7EFF8", foreground: "#1F4C87" };
    case "score":
      return { background: ChoirTheme.goldTint, foreground: ChoirTheme.gold };
    case "lyrics":
      return { background: ChoirTheme.plumTint, foreground: ChoirTheme.plum };
    default:
      return { background: ChoirTheme.surfaceMuted, foreground: ChoirTheme.inkMuted };
  }
}

export interface ChoirResourceCardProps {
  resource: ChoirResource;
  /** Bookmark state, owned by the screen so the two stay in sync. */
  isFavorited?: boolean;
  onToggleFavorite?: (resource: ChoirResource) => void;
  /** Starts playback via the persistent player. Only offered for playable kinds. */
  onPlay?: (resource: ChoirResource) => void;
  /** Shown as a small badge, e.g. "Recommended this week". */
  badge?: string;
  compact?: boolean;
}

function ChoirResourceCardBase({
  resource,
  isFavorited = false,
  onToggleFavorite,
  onPlay,
  badge,
  compact = false,
}: ChoirResourceCardProps) {
  const router = useRouter();
  const kind = fileKindOf(resource);
  const tone = useAccentTone(kind);
  const duration = formatDuration(resource.duration);
  const isPlayable = (kind === "audio" || kind === "video") && Boolean(resourceFileUrl(resource));

  const openDetail = () => {
    router.push({ pathname: "/choir-detail", params: { id: String(resource.id) } });
  };

  return (
    <Pressable
      onPress={openDetail}
      accessibilityRole="button"
      accessibilityLabel={`${resource.title}. ${resource.category}. ${
        KIND_LABEL[kind] ?? "File"
      }. Open resource details.`}
      style={({ pressed }) => [
        styles.card,
        compact && styles.cardCompact,
        pressed && styles.cardPressed,
      ]}
    >
      {badge ? (
        <View style={styles.badge}>
          <Text style={styles.badgeText}>{badge}</Text>
        </View>
      ) : null}

      <View style={styles.header}>
        <View style={[styles.iconWell, { backgroundColor: tone.background }]}>
          <Ionicons
            name={KIND_ICON[kind] ?? "document-outline"}
            size={compact ? 18 : 20}
            color={tone.foreground}
          />
        </View>

        <View style={styles.titleBlock}>
          <Text style={styles.title} numberOfLines={2}>
            {resource.title}
          </Text>
          <Text style={styles.category} numberOfLines={1}>
            {resource.category}
          </Text>
        </View>

        {onPlay && isPlayable ? (
          <Pressable
            onPress={() => onPlay(resource)}
            hitSlop={10}
            accessibilityRole="button"
            accessibilityLabel={`Play ${resource.title}`}
            style={styles.favorite}
          >
            <Ionicons name="play-circle" size={24} color={ChoirTheme.green} />
          </Pressable>
        ) : null}

        {onToggleFavorite ? (
          <Pressable
            onPress={() => onToggleFavorite(resource)}
            hitSlop={10}
            accessibilityRole="button"
            accessibilityState={{ selected: isFavorited }}
            accessibilityLabel={
              isFavorited ? `Remove ${resource.title} from bookmarks` : `Bookmark ${resource.title}`
            }
            style={styles.favorite}
          >
            <Ionicons
              name={isFavorited ? "bookmark" : "bookmark-outline"}
              size={20}
              color={isFavorited ? ChoirTheme.green : ChoirTheme.inkFaint}
            />
          </Pressable>
        ) : null}
      </View>

      {!compact && resource.composer ? (
        <Text style={styles.composer} numberOfLines={1}>
          {resource.composer}
        </Text>
      ) : null}

      <View style={styles.metaRow}>
        <View style={styles.chip}>
          <Text style={styles.chipText}>{KIND_LABEL[kind] ?? "File"}</Text>
        </View>
        {resource.language ? (
          <View style={styles.chip}>
            <Text style={styles.chipText}>{resource.language}</Text>
          </View>
        ) : null}
        {duration ? (
          <View style={styles.chip}>
            <Ionicons name="time-outline" size={12} color={ChoirTheme.inkMuted} />
            <Text style={styles.chipText}>{duration}</Text>
          </View>
        ) : null}
        {typeof resource.download_count === "number" && resource.download_count > 0 ? (
          <View style={styles.chip}>
            <Ionicons name="arrow-down-circle-outline" size={12} color={ChoirTheme.inkMuted} />
            <Text style={styles.chipText}>{resource.download_count}</Text>
          </View>
        ) : null}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: ChoirTheme.surface,
    borderRadius: ChoirRadius.md,
    borderWidth: 1,
    borderColor: ChoirTheme.border,
    padding: ChoirSpace.lg,
    marginBottom: ChoirSpace.md,
    ...ChoirShadow,
  },
  cardCompact: {
    padding: ChoirSpace.md,
    marginBottom: ChoirSpace.sm,
  },
  cardPressed: {
    opacity: 0.85,
    transform: [{ scale: 0.995 }],
  },
  badge: {
    alignSelf: "flex-start",
    backgroundColor: ChoirTheme.goldTint,
    borderRadius: ChoirRadius.pill,
    paddingHorizontal: 10,
    paddingVertical: 3,
    marginBottom: ChoirSpace.sm,
  },
  badgeText: {
    color: ChoirTheme.gold,
    fontSize: ChoirType.micro,
    fontWeight: "700",
    letterSpacing: 0.3,
    textTransform: "uppercase",
  },
  header: {
    flexDirection: "row",
    alignItems: "flex-start",
  },
  iconWell: {
    width: 40,
    height: 40,
    borderRadius: ChoirRadius.sm,
    alignItems: "center",
    justifyContent: "center",
    marginRight: ChoirSpace.md,
  },
  titleBlock: {
    flex: 1,
    paddingRight: ChoirSpace.sm,
  },
  title: {
    fontSize: ChoirType.cardTitle,
    fontWeight: "700",
    color: ChoirTheme.ink,
    lineHeight: 22,
  },
  category: {
    fontSize: ChoirType.meta,
    color: ChoirTheme.green,
    fontWeight: "600",
    marginTop: 2,
  },
  favorite: {
    minWidth: MinTouchTarget,
    minHeight: MinTouchTarget,
    alignItems: "center",
    justifyContent: "center",
  },
  composer: {
    fontSize: ChoirType.meta,
    color: ChoirTheme.inkMuted,
    marginTop: ChoirSpace.sm,
  },
  metaRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    marginTop: ChoirSpace.md,
    gap: ChoirSpace.xs,
  },
  chip: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: ChoirTheme.surfaceMuted,
    borderRadius: ChoirRadius.pill,
    paddingHorizontal: 9,
    paddingVertical: 4,
    gap: 4,
  },
  chipText: {
    color: ChoirTheme.inkMuted,
    fontSize: ChoirType.micro,
    fontWeight: "600",
  },
});

export const ChoirResourceCard = React.memo(ChoirResourceCardBase);