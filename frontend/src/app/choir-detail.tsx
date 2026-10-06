/**
 * Choir resource detail.
 *
 * Was a title, one line of metadata and an "Open Resource" button. It is now the
 * page a choir member actually works from: what the piece is, who wrote it, the
 * key and tempo before rehearsal starts, the lyrics if they are attached, the
 * prayer traditionally said at that point of Mass, and the actions (open, save
 * offline, bookmark, report).
 *
 * Two things this screen deliberately does not do:
 *   - Claim a file is playable. `resourceFileUrl` validates the stored URL and
 *     the result is handed to the OS handler, because `file_url` is a value this
 *     client does not control.
 *   - Report a missing file as an error state. A resource with no usable URL
 *     renders its metadata with an explicit "no file attached" notice, which is a
 *     true statement about the record rather than a failure to load.
 */

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";

import { ErrorState } from "@/components/ScreenStates";
import { ReportButton } from "@/components/ReportButton";
import { useChoirPlayer } from "@/components/choir/ChoirPlayerProvider";
import {
  ChoirRadius,
  ChoirShadow,
  ChoirSpace,
  ChoirTheme,
  ChoirType,
  MaxChoirContentWidth,
  MinTouchTarget,
} from "@/constants/choirTheme";
import { prayersForCategory } from "@/config/choirPrayers";
import { classifyRequestFailure, type RequestFailure } from "@/lib/requestFailure";
import { favoriteService } from "@/services/favoriteService";
import {
  fetchResource,
  fetchResources,
  fileKindOf,
  formatDuration,
  resourceFileUrl,
  type ChoirResource,
} from "@/services/choirService";
import { cacheResource } from "@/services/offlineStore";
import { api } from "@/lib/api";

const KIND_LABEL: Record<string, string> = {
  audio: "Audio recording",
  video: "Video",
  pdf: "PDF document",
  score: "Score",
  lyrics: "Lyrics",
  other: "File",
};

function formatBytes(bytes: number | null): string | null {
  if (bytes == null || bytes <= 0) {
    return null;
  }
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value < 10 && unit > 0 ? value.toFixed(1) : Math.round(value)} ${units[unit]}`;
}

function MetaRow({ label, value }: { label: string; value: string | null }) {
  if (!value) {
    return null;
  }
  return (
    <View style={styles.metaRow}>
      <Text style={styles.metaLabel}>{label}</Text>
      <Text style={styles.metaValue}>{value}</Text>
    </View>
  );
}

export default function ChoirDetail() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const router = useRouter();
  const player = useChoirPlayer();

  const [resource, setResource] = useState<ChoirResource | null>(null);
  const [related, setRelated] = useState<ChoirResource[]>([]);
  const [loading, setLoading] = useState(true);
  const [failure, setFailure] = useState<RequestFailure | null>(null);
  const [missingParam, setMissingParam] = useState(false);

  const [isFavorited, setIsFavorited] = useState(false);
  const [favoriteId, setFavoriteId] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [noticeTone, setNoticeTone] = useState<"info" | "error">("info");
  const [busyAction, setBusyAction] = useState<"download" | "open" | null>(null);

  const resourceId = Number(id);

  const load = useCallback(async () => {
    if (!id || !Number.isFinite(resourceId)) {
      setMissingParam(true);
      setFailure(null);
      setResource(null);
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setFailure(null);
      setNotice(null);

      const result = await fetchResource(resourceId);
      if (result.kind === "failure") {
        setResource(null);
        // The backend's own `detail` is used, so the deliberate 404 that
        // `can_view_choir_resource` returns for a permission failure stays
        // distinguishable from a mistyped id.
        setFailure(result.failure);
        return;
      }

      setResource(result.data);

      // Never lets an auth failure take down the page: bookmarks degrade only.
      const favorites = await favoriteService.getFavoritesOptional();
      const favorite = favorites.find(
        (f) => f.resource_type === "choir" && f.target_resource_id === resourceId,
      );
      setIsFavorited(Boolean(favorite));
      setFavoriteId(favorite ? favorite.id : null);

      // Other resources in the same category, so a choir can compare options.
      const siblings = await fetchResources({
        category: result.data.category,
        sort: "popular",
        limit: 4,
      });
      setRelated(
        siblings.kind === "ok"
          ? siblings.data.filter((row) => row.id !== resourceId).slice(0, 3)
          : [],
      );
    } finally {
      setLoading(false);
    }
  }, [id, resourceId]);

  useEffect(() => {
    void Promise.resolve().then(() => load());
  }, [load]);

  const toggleFavorite = async () => {
    if (!resource) {
      return;
    }
    try {
      if (isFavorited && favoriteId) {
        await favoriteService.deleteFavorite(favoriteId);
        setIsFavorited(false);
        setFavoriteId(null);
      } else {
        const created = await favoriteService.createFavorite("choir", resource.id);
        setIsFavorited(true);
        setFavoriteId(created.id);
      }
      setNoticeTone("info");
      setNotice(isFavorited ? "Removed from bookmarks." : "Saved to your bookmarks.");
    } catch (error) {
      const classified = classifyRequestFailure(error, {
        fallbackNotFound: "That resource is not available.",
        fallbackMessage: "Could not update your bookmark. Check your connection and try again.",
      });
      setNoticeTone("error");
      if (classified.kind === "unauthorized") {
        setNotice("Sign in to bookmark choir resources.");
      } else {
        setNotice(classified.message);
      }
    }
  };

  const openFile = async () => {
    if (!resource) {
      return;
    }
    // Delegated to the persistent player rather than opening inline: this is
    // the same action as tapping Play on the library card, so it must produce
    // the same behaviour -- same validation, same failure text, and the bar
    // stays put when the member navigates back to browsing.
    setBusyAction("open");
    try {
      await player.play(resource);
    } finally {
      setBusyAction(null);
    }
  };

  const saveOffline = async () => {
    if (!resource || !resource.file_url) {
      setNoticeTone("error");
      setNotice("This resource has no file to save.");
      return;
    }
    setBusyAction("download");
    setNotice(null);
    try {
      await cacheResource({
        id: resource.id,
        title: resource.title,
        file_url: resource.file_url,
        file_type: resource.file_type ?? undefined,
      });
      // Recording the download is a separate call and must not undo a successful
      // save if it fails (it can when a signed-out visitor hits a protected route).
      try {
        await api.post(`/api/downloads/${resource.id}`);
      } catch {
        // The file is cached; only the counter was not updated.
      }
      setNoticeTone("info");
      setNotice("Saved for offline use on this device.");
    } catch (error) {
      const classified = classifyRequestFailure(error, {
        fallbackNotFound: "That resource is not available.",
        fallbackMessage: "The file could not be saved. Check your connection and try again.",
      });
      setNoticeTone("error");
      setNotice(classified.message);
    } finally {
      setBusyAction(null);
    }
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={ChoirTheme.green} />
        <Text style={styles.centerText}>Loading resource…</Text>
      </View>
    );
  }

  if (missingParam) {
    return (
      <View style={styles.center}>
        <ErrorState
          message="No resource was selected."
          onRetry={() => router.back()}
          retryLabel="Go back"
        />
      </View>
    );
  }

  if (failure) {
    return (
      <View style={styles.center}>
        <ErrorState
          message={failure.message}
          onRetry={failure.retryable ? () => void load() : () => router.back()}
          retryLabel={failure.retryable ? "Try again" : "Go back"}
        />
      </View>
    );
  }

  if (!resource) {
    return (
      <View style={styles.center}>
        <ErrorState
          message="This resource could not be loaded."
          onRetry={() => void load()}
        />
      </View>
    );
  }

  const kind = fileKindOf(resource);
  const duration = formatDuration(resource.duration);
  const size = formatBytes(resource.file_size);
  const prayers = prayersForCategory(resource.category);
  const hasFile = Boolean(resourceFileUrl(resource));

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.page}>
      <View style={styles.content}>
        {/* --- Header --- */}
        <Pressable
          onPress={() => router.back()}
          hitSlop={12}
          accessibilityRole="button"
          accessibilityLabel="Go back"
          style={styles.back}
        >
          <Ionicons name="chevron-back" size={20} color={ChoirTheme.green} />
          <Text style={styles.backText}>Library</Text>
        </Pressable>

        <View style={styles.header}>
          <View style={styles.headerText}>
            <Text style={styles.category}>{resource.category}</Text>
            <Text style={styles.title}>{resource.title}</Text>
            {resource.alternative_title ? (
              <Text style={styles.altTitle}>also “{resource.alternative_title}”</Text>
            ) : null}
          </View>
          <Pressable
            onPress={() => void toggleFavorite()}
            accessibilityRole="button"
            accessibilityState={{ selected: isFavorited }}
            accessibilityLabel={isFavorited ? "Remove bookmark" : "Add bookmark"}
            style={styles.bookmark}
          >
            <Ionicons
              name={isFavorited ? "bookmark" : "bookmark-outline"}
              size={24}
              color={isFavorited ? ChoirTheme.green : ChoirTheme.inkFaint}
            />
          </Pressable>
        </View>

        {notice ? (
          <View
            style={[
              styles.notice,
              noticeTone === "error" ? styles.noticeError : styles.noticeInfo,
            ]}
            accessibilityLiveRegion="polite"
          >
            <Ionicons
              name={noticeTone === "error" ? "alert-circle-outline" : "information-circle-outline"}
              size={16}
              color={noticeTone === "error" ? ChoirTheme.danger : ChoirTheme.green}
            />
            <Text
              style={[
                styles.noticeText,
                noticeTone === "error" ? styles.noticeTextError : styles.noticeTextInfo,
              ]}
            >
              {notice}
            </Text>
          </View>
        ) : null}

        {/* --- Actions --- */}
        <View style={styles.actions}>
          <Pressable
            onPress={() => void openFile()}
            disabled={!hasFile || busyAction !== null}
            accessibilityRole="button"
            accessibilityLabel={hasFile ? "Open resource" : "No file attached"}
            style={[styles.primaryAction, !hasFile && styles.actionDisabled]}
          >
            <Ionicons name="play-circle-outline" size={20} color={ChoirTheme.white} />
            <Text style={styles.primaryActionText}>
              {busyAction === "open" ? "Opening…" : "Open"}
            </Text>
          </Pressable>

          <Pressable
            onPress={() => void saveOffline()}
            disabled={!hasFile || busyAction !== null}
            accessibilityRole="button"
            accessibilityLabel={hasFile ? "Save for offline use" : "No file attached"}
            style={[styles.secondaryAction, !hasFile && styles.actionDisabled]}
          >
            <Ionicons
              name={busyAction === "download" ? "hourglass-outline" : "download-outline"}
              size={20}
              color={hasFile ? ChoirTheme.green : ChoirTheme.inkFaint}
            />
            <Text style={[styles.secondaryActionText, !hasFile && styles.actionDisabledText]}>
              {busyAction === "download" ? "Saving…" : "Save offline"}
            </Text>
          </Pressable>
        </View>

        {!hasFile ? (
          <Text style={styles.noFileNotice}>
            No playable file is attached to this record. The details below are what the library
            holds.
          </Text>
        ) : null}

        {/* --- Description --- */}
        {resource.description ? (
          <View style={styles.block}>
            <Text style={styles.blockTitle}>About this resource</Text>
            <Text style={styles.body}>{resource.description}</Text>
          </View>
        ) : null}

        {/* --- Metadata --- */}
        <View style={styles.block}>
          <Text style={styles.blockTitle}>Details</Text>
          <MetaRow label="Format" value={KIND_LABEL[kind] ?? "File"} />
          <MetaRow label="Language" value={resource.language} />
          <MetaRow label="Composer" value={resource.composer} />
          <MetaRow label="Author" value={resource.author} />
          <MetaRow label="Arranger" value={resource.arranger} />
          <MetaRow label="Voice part" value={resource.voice_part} />
          <MetaRow label="Key" value={resource.key_signature} />
          <MetaRow label="Tempo" value={resource.tempo} />
          <MetaRow label="Season" value={resource.season} />
          <MetaRow label="Duration" value={duration} />
          <MetaRow label="File size" value={size} />
          <MetaRow
            label="Downloads"
            value={
              typeof resource.download_count === "number" ? String(resource.download_count) : null
            }
          />
        </View>

        {/* --- Lyrics --- */}
        {resource.lyrics ? (
          <View style={styles.block}>
            <Text style={styles.blockTitle}>Lyrics</Text>
            <Text style={styles.lyrics}>{resource.lyrics}</Text>
          </View>
        ) : null}

        {/* --- Prayer for this part of Mass --- */}
        {prayers.length > 0 ? (
          <View style={styles.block}>
            <Text style={styles.blockTitle}>Pray with this resource</Text>
            <Text style={styles.prayerIntro}>
              Traditionally said at this point of the Mass.
            </Text>
            {prayers.map((prayer) => (
              <View key={prayer.id} style={styles.prayerCard}>
                <Text style={styles.prayerTitle}>
                  {prayer.title}
                  {prayer.latinTitle ? (
                    <Text style={styles.prayerLatin}> · {prayer.latinTitle}</Text>
                  ) : null}
                </Text>
                {prayer.rubric ? <Text style={styles.prayerRubric}>{prayer.rubric}</Text> : null}
                <Text style={styles.prayerBody}>{prayer.body}</Text>
              </View>
            ))}
          </View>
        ) : null}

        <ReportButton resourceType="choir" resourceId={resource.id} />

        {/* --- Related --- */}
        {related.length > 0 ? (
          <View style={styles.block}>
            <Text style={styles.blockTitle}>More in {resource.category}</Text>
            {related.map((row) => (
              <Pressable
                key={row.id}
                onPress={() => router.replace({ pathname: "/choir-detail", params: { id: String(row.id) } })}
                accessibilityRole="button"
                accessibilityLabel={`Open ${row.title}`}
                style={({ pressed }) => [styles.relatedRow, pressed && styles.relatedRowPressed]}
              >
                <Ionicons name="musical-notes-outline" size={16} color={ChoirTheme.green} />
                <Text style={styles.relatedTitle} numberOfLines={1}>
                  {row.title}
                </Text>
                <Ionicons name="chevron-forward" size={16} color={ChoirTheme.inkFaint} />
              </Pressable>
            ))}
          </View>
        ) : null}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: ChoirTheme.canvas,
  },
  page: {
    paddingBottom: ChoirSpace.xxl * 2,
  },
  content: {
    paddingHorizontal: ChoirSpace.lg,
    paddingTop: ChoirSpace.lg,
    alignSelf: "center",
    width: "100%",
    maxWidth: MaxChoirContentWidth,
  },
  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: ChoirSpace.xl,
    backgroundColor: ChoirTheme.canvas,
  },
  centerText: {
    marginTop: ChoirSpace.md,
    color: ChoirTheme.inkMuted,
  },

  back: {
    flexDirection: "row",
    alignItems: "center",
    gap: ChoirSpace.xs,
    minHeight: MinTouchTarget,
  },
  backText: {
    color: ChoirTheme.green,
    fontWeight: "700",
    fontSize: ChoirType.meta,
  },

  header: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginTop: ChoirSpace.md,
    marginBottom: ChoirSpace.lg,
  },
  headerText: {
    flex: 1,
  },
  category: {
    fontSize: ChoirType.micro,
    letterSpacing: 1,
    textTransform: "uppercase",
    color: ChoirTheme.gold,
    fontWeight: "700",
  },
  title: {
    fontSize: 28,
    fontWeight: "800",
    color: ChoirTheme.greenDark,
    marginTop: ChoirSpace.xs,
    lineHeight: 34,
  },
  altTitle: {
    fontSize: ChoirType.meta,
    color: ChoirTheme.inkFaint,
    marginTop: ChoirSpace.xs,
    fontStyle: "italic",
  },
  bookmark: {
    minWidth: MinTouchTarget,
    minHeight: MinTouchTarget,
    alignItems: "center",
    justifyContent: "center",
    marginLeft: ChoirSpace.md,
  },

  notice: {
    flexDirection: "row",
    alignItems: "center",
    gap: ChoirSpace.sm,
    borderRadius: ChoirRadius.sm,
    borderWidth: 1,
    padding: ChoirSpace.md,
    marginBottom: ChoirSpace.lg,
  },
  noticeInfo: {
    backgroundColor: ChoirTheme.greenTint,
    borderColor: "#BEDCC7",
  },
  noticeError: {
    backgroundColor: ChoirTheme.dangerTint,
    borderColor: "#F3C2BD",
  },
  noticeText: {
    flex: 1,
    fontSize: ChoirType.meta,
    lineHeight: 19,
  },
  noticeTextInfo: {
    color: ChoirTheme.greenDark,
  },
  noticeTextError: {
    color: ChoirTheme.danger,
  },

  actions: {
    flexDirection: "row",
    gap: ChoirSpace.md,
    marginBottom: ChoirSpace.md,
  },
  primaryAction: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: ChoirSpace.sm,
    backgroundColor: ChoirTheme.green,
    borderRadius: ChoirRadius.sm,
    minHeight: MinTouchTarget + 4,
  },
  primaryActionText: {
    color: ChoirTheme.white,
    fontWeight: "700",
    fontSize: ChoirType.body,
  },
  secondaryAction: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: ChoirSpace.sm,
    borderWidth: 1,
    borderColor: ChoirTheme.green,
    borderRadius: ChoirRadius.sm,
    minHeight: MinTouchTarget + 4,
  },
  secondaryActionText: {
    color: ChoirTheme.green,
    fontWeight: "700",
    fontSize: ChoirType.body,
  },
  actionDisabled: {
    opacity: 0.45,
    backgroundColor: ChoirTheme.surfaceMuted,
    borderColor: ChoirTheme.border,
  },
  actionDisabledText: {
    color: ChoirTheme.inkFaint,
  },
  noFileNotice: {
    fontSize: ChoirType.meta,
    color: ChoirTheme.inkMuted,
    lineHeight: 19,
    backgroundColor: ChoirTheme.goldTint,
    borderRadius: ChoirRadius.sm,
    padding: ChoirSpace.md,
    marginBottom: ChoirSpace.lg,
  },

  block: {
    marginTop: ChoirSpace.xl,
  },
  blockTitle: {
    fontSize: ChoirType.cardTitle,
    fontWeight: "700",
    color: ChoirTheme.ink,
    marginBottom: ChoirSpace.md,
  },
  body: {
    fontSize: ChoirType.body,
    color: ChoirTheme.inkMuted,
    lineHeight: 23,
  },
  lyrics: {
    fontSize: ChoirType.body,
    color: ChoirTheme.ink,
    lineHeight: 25,
    backgroundColor: ChoirTheme.surface,
    borderRadius: ChoirRadius.sm,
    borderWidth: 1,
    borderColor: ChoirTheme.border,
    padding: ChoirSpace.lg,
  },

  metaRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    paddingVertical: ChoirSpace.sm,
    borderBottomWidth: 1,
    borderBottomColor: ChoirTheme.border,
    gap: ChoirSpace.lg,
  },
  metaLabel: {
    fontSize: ChoirType.meta,
    color: ChoirTheme.inkMuted,
    flexShrink: 0,
  },
  metaValue: {
    fontSize: ChoirType.meta,
    color: ChoirTheme.ink,
    fontWeight: "600",
    flex: 1,
    textAlign: "right",
  },

  prayerIntro: {
    fontSize: ChoirType.micro,
    color: ChoirTheme.inkFaint,
    marginTop: -ChoirSpace.sm,
    marginBottom: ChoirSpace.md,
  },
  prayerCard: {
    backgroundColor: ChoirTheme.surface,
    borderRadius: ChoirRadius.sm,
    borderLeftWidth: 3,
    borderLeftColor: ChoirTheme.plum,
    borderWidth: 1,
    borderColor: ChoirTheme.border,
    padding: ChoirSpace.lg,
    marginBottom: ChoirSpace.md,
    ...ChoirShadow,
  },
  prayerTitle: {
    fontSize: ChoirType.meta,
    fontWeight: "700",
    color: ChoirTheme.plum,
  },
  prayerLatin: {
    fontWeight: "400",
    color: ChoirTheme.inkFaint,
  },
  prayerRubric: {
    fontSize: ChoirType.micro,
    color: ChoirTheme.inkFaint,
    fontStyle: "italic",
    marginTop: 2,
  },
  prayerBody: {
    fontSize: ChoirType.body,
    color: ChoirTheme.ink,
    lineHeight: 24,
    marginTop: ChoirSpace.sm,
  },

  relatedRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: ChoirSpace.md,
    backgroundColor: ChoirTheme.surface,
    borderRadius: ChoirRadius.sm,
    borderWidth: 1,
    borderColor: ChoirTheme.border,
    paddingHorizontal: ChoirSpace.lg,
    minHeight: MinTouchTarget + 6,
    marginBottom: ChoirSpace.sm,
  },
  relatedRowPressed: {
    opacity: 0.8,
  },
  relatedTitle: {
    flex: 1,
    fontSize: ChoirType.meta,
    color: ChoirTheme.ink,
    fontWeight: "600",
  },
});