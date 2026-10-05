import { useCallback, useEffect, useState } from "react";
import { Alert, ScrollView, StyleSheet, Text, View, Pressable, Linking } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { api } from "@/lib/api";
import { API_URL } from "@/config/api";
import { classifyRequestFailure, RequestFailure } from "@/lib/requestFailure";
import { safeExternalUrl } from "@/lib/externalUrl";
import { Ionicons } from "@expo/vector-icons";
import { favoriteService } from "@/services/favoriteService";
import { ReportButton } from "@/components/ReportButton";
import { ErrorState, LoadingState } from "@/components/ScreenStates";

export default function ChoirDetail() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const router = useRouter();
  const [resource, setResource] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [failure, setFailure] = useState<RequestFailure | null>(null);
  const [missingParam, setMissingParam] = useState(false);
  const [isFavorited, setIsFavorited] = useState(false);
  const [favoriteId, setFavoriteId] = useState<number | null>(null);

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
      const res = await api.get(`/api/choir/${resourceId}`);
      setResource(res.data);

      const favorites = await favoriteService.getFavoritesOptional();
      const favorite = favorites.find(
        (f) => f.resource_type === "choir" && f.target_resource_id === resourceId,
      );
      setIsFavorited(Boolean(favorite));
      setFavoriteId(favorite ? favorite.id : null);
    } catch (error: unknown) {
      setResource(null);
      // The backend's own detail is used rather than a fixed string, so the
      // deliberate 404 that `can_view_choir_resource` returns for a permission
      // failure is no longer indistinguishable from a mistyped id.
      setFailure(
        classifyRequestFailure(error, {
          fallbackNotFound: "That choir resource is not available.",
        }),
      );
    } finally {
      setLoading(false);
    }
  }, [id, resourceId]);

  useEffect(() => {
    void Promise.resolve().then(() => load());
  }, [load]);

  async function toggleFavorite() {
    if (!resource) return;
    try {
      if (isFavorited && favoriteId) {
        await favoriteService.deleteFavorite(favoriteId);
        setIsFavorited(false);
        setFavoriteId(null);
      } else {
        const newFav = await favoriteService.createFavorite("choir", resource.id);
        setIsFavorited(true);
        setFavoriteId(newFav.id);
      }
    } catch {
      Alert.alert("Could not update bookmark", "Please try again.");
    }
  }

  /**
   * Open the stored file.
   *
   * `file_url` is a value this client does not control, and it was previously
   * handed to the OS URL handler with no validation at all: no null check, no
   * scheme allowlist, and no `try`/`catch` around a promise that rejects whenever
   * the device has no handler. A rejected promise there was an unhandled
   * rejection the member never saw.
   */
  async function openFile() {
    const resolved = safeExternalUrl(resource?.file_url, API_URL);
    if (!resolved) {
      Alert.alert(
        "Unavailable",
        "This resource does not have a file, or its address is not supported.",
      );
      return;
    }
    try {
      if (!(await Linking.canOpenURL(resolved))) {
        Alert.alert(
          "Cannot Open",
          "This resource cannot be opened on this device.",
        );
        return;
      }
      await Linking.openURL(resolved);
    } catch {
      Alert.alert("Error", "Unable to open this resource.");
    }
  }

  if (loading) return <LoadingState label="Loading resource…" />;

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
        <ErrorState message="This resource could not be loaded." onRetry={() => void load()} />
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>{resource.title}</Text>
        <Pressable
          onPress={() => void toggleFavorite()}
          accessibilityRole="button"
          accessibilityLabel={isFavorited ? "Remove bookmark" : "Add bookmark"}
        >
          <Ionicons
            name={isFavorited ? "bookmark" : "bookmark-outline"}
            size={28}
            color="#0B6623"
          />
        </Pressable>
      </View>
      <Text style={styles.meta}>{resource.category} · {resource.file_type}</Text>
      {resource.description ? (
        <Text style={styles.content}>{resource.description}</Text>
      ) : null}

      <Pressable
        style={styles.button}
        onPress={() => void openFile()}
        accessibilityRole="button"
      >
        <Text style={styles.buttonText}>Open Resource</Text>
      </Pressable>

      <ReportButton resourceType="choir" resourceId={resource.id} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({ 
  container: { padding: 20, backgroundColor: "#fff" }, 
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  center: { flex: 1, justifyContent: "center", alignItems: "center", padding: 24 }, 
  title: { fontSize: 28, fontWeight: "800", color: "#0B6623" }, 
  meta: { color: "#666", marginTop: 8, fontWeight: "700" }, 
  content: { color: "#444", lineHeight: 23, marginTop: 15 },
  button: { marginTop: 20, backgroundColor: '#0B6623', padding: 15, borderRadius: 8, alignItems: 'center' },
  buttonText: { color: '#fff', fontWeight: 'bold' }
});
