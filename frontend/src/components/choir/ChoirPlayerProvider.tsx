/**
 * Persistent "now playing" bar for the choir library.
 *
 * A choir member browses by ear: they start a piece, go back to the library to
 * find the next one, and expect the current piece to still be there. The detail
 * screen could not own that state because it unmounts on navigation, so the
 * active resource lives in a provider mounted at the app root instead.
 *
 * Scope note, stated plainly rather than implied: this bar does not decode audio
 * itself. `expo-audio` is not a dependency of this project, and the stored
 * `file_url` is server-controlled, so playback is delegated to the OS handler
 * through `Linking` after the URL has been validated. What the bar provides is
 * persistence, the actions, and an honest state -- it never claims to be
 * playing when nothing is playing.
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";
import { ActivityIndicator, Linking, Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";

import { api } from "@/lib/api";
import { cacheResource } from "@/services/offlineStore";
import {
  fileKindOf,
  formatDuration,
  resourceFileUrl,
  type ChoirResource,
} from "@/services/choirService";
import {
  ChoirRadius,
  ChoirShadow,
  ChoirSpace,
  ChoirTheme,
  ChoirType,
  MinTouchTarget,
} from "@/constants/choirTheme";

interface ChoirPlayerValue {
  active: ChoirResource | null;
  play: (resource: ChoirResource) => Promise<void>;
  stop: () => void;
}

const ChoirPlayerContext = createContext<ChoirPlayerValue>({
  active: null,
  play: async () => undefined,
  stop: () => undefined,
});

export function useChoirPlayer(): ChoirPlayerValue {
  return useContext(ChoirPlayerContext);
}

export function ChoirPlayerProvider({ children }: { children: React.ReactNode }) {
  const [active, setActive] = useState<ChoirResource | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const play = useCallback(async (resource: ChoirResource) => {
    setActive(resource);
    setError(null);

    const resolved = resourceFileUrl(resource);
    if (!resolved) {
      setError("This resource has no file attached.");
      return;
    }

    setBusy(true);
    try {
      if (!(await Linking.canOpenURL(resolved))) {
        setError("This device cannot open that file type.");
        return;
      }
      await Linking.openURL(resolved);
    } catch {
      setError("Could not open this file.");
    } finally {
      setBusy(false);
    }
  }, []);

  const stop = useCallback(() => {
    setActive(null);
    setError(null);
  }, []);

  /**
   * Save the active resource for offline use.
   *
   * Defined here rather than in the bar because `busy`/`error` belong to the
   * provider; the failure text has to reach the bar that displays it.
   */
  const save = useCallback(async () => {
    if (!active?.file_url) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await cacheResource({
        id: active.id,
        title: active.title,
        file_url: active.file_url,
        file_type: active.file_type ?? undefined,
      });
      try {
        await api.post(`/api/downloads/${active.id}`);
      } catch {
        // The file is saved on the device; only the counter was not updated.
      }
    } catch {
      setError("The file could not be saved on this device.");
    } finally {
      setBusy(false);
    }
  }, [active]);

  const value = useMemo<ChoirPlayerValue>(
    () => ({ active, play, stop }),
    [active, play, stop],
  );

  return (
    <ChoirPlayerContext.Provider value={value}>
      <ChoirPlayerBar
        active={active}
        busy={busy}
        error={error}
        onPlay={play}
        onSave={save}
        onStop={stop}
      />
      {children}
    </ChoirPlayerContext.Provider>
  );
}

function ChoirPlayerBar({
  active,
  busy,
  error,
  onPlay,
  onSave,
  onStop,
}: {
  active: ChoirResource | null;
  busy: boolean;
  error: string | null;
  onPlay: (resource: ChoirResource) => Promise<void>;
  onSave: () => Promise<void>;
  onStop: () => void;
}) {
  const router = useRouter();
  // Rendering nothing when idle is deliberate: the bar must not take vertical
  // space on any screen when no choir resource is active.
  if (!active) {
    return null;
  }

  const kind = fileKindOf(active);
  const duration = formatDuration(active.duration);

  return (
    <View style={styles.wrap} accessibilityLiveRegion="polite">
      <View style={styles.bar}>
        <View style={[styles.art, { backgroundColor: kind === "audio" ? ChoirTheme.greenTint : ChoirTheme.surfaceMuted }]}>
          <Ionicons
            name={kind === "audio" ? "musical-notes" : "document-text"}
            size={18}
            color={ChoirTheme.green}
          />
        </View>

        <Pressable
          style={styles.textBlock}
          accessibilityRole="button"
          accessibilityLabel={`Open ${active.title} details`}
          onPress={() => router.push({ pathname: "/choir-detail", params: { id: String(active.id) } })}
        >
          <Text style={styles.title} numberOfLines={1}>
            {active.title}
          </Text>
          <Text style={styles.subtitle} numberOfLines={1}>
            {active.category}
            {duration ? ` · ${duration}` : ""}
          </Text>
        </Pressable>

        {busy ? (
          <ActivityIndicator size="small" color={ChoirTheme.green} style={styles.spinner} />
        ) : (
          <>
            <Pressable
              onPress={() => void onPlay(active)}
              hitSlop={8}
              accessibilityRole="button"
              accessibilityLabel={`Play ${active.title}`}
              style={styles.action}
            >
              <Ionicons name="play" size={18} color={ChoirTheme.green} />
            </Pressable>
            <Pressable
              onPress={() => void onSave()}
              hitSlop={8}
              accessibilityRole="button"
              accessibilityLabel={`Save ${active.title} for offline use`}
              style={styles.action}
            >
              <Ionicons name="download-outline" size={18} color={ChoirTheme.green} />
            </Pressable>
          </>
        )}

        <Pressable
          onPress={onStop}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel="Stop and close the player"
          style={styles.action}
        >
          <Ionicons name="close" size={18} color={ChoirTheme.inkFaint} />
        </Pressable>
      </View>

      {error ? (
        <Text style={styles.error} accessibilityRole="alert">
          {error}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
  },
  bar: {
    flexDirection: "row",
    alignItems: "center",
    gap: ChoirSpace.sm,
    margin: ChoirSpace.md,
    paddingHorizontal: ChoirSpace.md,
    paddingVertical: ChoirSpace.sm,
    backgroundColor: ChoirTheme.surface,
    borderRadius: ChoirRadius.md,
    borderWidth: 1,
    borderColor: ChoirTheme.border,
    minHeight: MinTouchTarget + 10,
    ...ChoirShadow,
  },
  art: {
    width: 34,
    height: 34,
    borderRadius: ChoirRadius.sm,
    alignItems: "center",
    justifyContent: "center",
  },
  textBlock: {
    flex: 1,
    justifyContent: "center",
  },
  title: {
    fontSize: ChoirType.meta,
    fontWeight: "700",
    color: ChoirTheme.ink,
  },
  subtitle: {
    fontSize: ChoirType.micro,
    color: ChoirTheme.inkMuted,
  },
  spinner: {
    marginHorizontal: ChoirSpace.xs,
  },
  action: {
    minWidth: MinTouchTarget,
    minHeight: MinTouchTarget,
    alignItems: "center",
    justifyContent: "center",
  },
  error: {
    marginHorizontal: ChoirSpace.lg,
    marginBottom: ChoirSpace.sm,
    fontSize: ChoirType.micro,
    color: ChoirTheme.danger,
  },
});