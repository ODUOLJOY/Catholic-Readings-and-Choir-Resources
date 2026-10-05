import { View, Text, StyleSheet, ScrollView, Pressable } from "react-native";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { classifyRequestFailure, RequestFailure } from "@/lib/requestFailure";
import { ReportButton } from "@/components/ReportButton";
import { favoriteService } from "@/services/favoriteService";
import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import { ErrorState, LoadingState } from "@/components/ScreenStates";

interface Saint {
  id: number;
  name: string;
  feast_date?: string;
  country?: string;
  patronage?: string;
  description?: string;
  biography?: string;
  liturgical_rank?: string;
}

export default function SaintDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [saint, setSaint] = useState<Saint | null>(null);
  const [loading, setLoading] = useState(true);
  const [failure, setFailure] = useState<RequestFailure | null>(null);
  const [missingParam, setMissingParam] = useState(false);
  const [isFavorited, setIsFavorited] = useState(false);
  const [favoriteId, setFavoriteId] = useState<number | null>(null);

  const saintId = Number(id);

  const load = useCallback(async () => {
    // `parseInt` of a malformed id yields NaN, which used to be sent straight to
    // the API as the literal path "NaN" and silently matched nothing.
    if (!id || !Number.isFinite(saintId)) {
      setMissingParam(true);
      setFailure(null);
      setSaint(null);
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setFailure(null);
      const res = await api.get<Saint>(`/api/saints/${saintId}`);
      setSaint(res.data);

      const favorites = await favoriteService.getFavoritesOptional();
      const favorite = favorites.find(
        (f) => f.resource_type === "saint" && f.target_resource_id === saintId,
      );
      setIsFavorited(Boolean(favorite));
      setFavoriteId(favorite ? favorite.id : null);
    } catch (error: unknown) {
      setSaint(null);
      // Previously the error was only logged, and the screen then rendered
      // "Saint not found." for a server it had never reached.
      setFailure(
        classifyRequestFailure(error, {
          fallbackNotFound: "That saint is not available.",
        }),
      );
    } finally {
      setLoading(false);
    }
  }, [id, saintId]);

  useEffect(() => {
    void Promise.resolve().then(() => load());
  }, [load]);

  async function toggleFavorite() {
    if (!saint) return;
    try {
      if (isFavorited && favoriteId) {
        await favoriteService.deleteFavorite(favoriteId);
        setIsFavorited(false);
        setFavoriteId(null);
      } else {
        const newFav = await favoriteService.createFavorite("saint", saint.id);
        setIsFavorited(true);
        setFavoriteId(newFav.id);
      }
    } catch {
      setFailure({
        kind: "server",
        message: "Could not update the bookmark. Please try again.",
        retryable: true,
      });
    }
  }

  if (loading) return <LoadingState label="Loading saint…" />;

  if (missingParam) {
    return (
      <View style={styles.center}>
        <ErrorState
          message="No saint was selected."
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

  if (!saint) {
    return (
      <View style={styles.center}>
        <ErrorState message="This saint could not be loaded." onRetry={() => void load()} />
      </View>
    );
  }

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>{saint.name}</Text>
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
      {saint.feast_date && <Text style={styles.meta}>Feast Date: {saint.feast_date}</Text>}
      {saint.liturgical_rank && <Text style={styles.meta}>Rank: {saint.liturgical_rank}</Text>}
      {saint.country && <Text style={styles.meta}>Country: {saint.country}</Text>}
      {saint.patronage && <Text style={styles.meta}>Patron of: {saint.patronage}</Text>}
      {saint.biography && <Text style={styles.biography}>{saint.biography}</Text>}
      {saint.description && <Text style={styles.description}>{saint.description}</Text>}
      <ReportButton resourceType="saint" resourceId={saint.id} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20, backgroundColor: "#fff" },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 15 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  title: { fontSize: 28, fontWeight: "800", color: "#0B6623" },
  meta: { fontSize: 16, color: "#666", marginBottom: 5 },
  biography: { fontSize: 16, color: "#333", marginTop: 20, lineHeight: 24 },
  description: { fontSize: 16, color: "#333", marginTop: 10, lineHeight: 24 }
});