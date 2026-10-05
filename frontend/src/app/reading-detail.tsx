import { useCallback, useEffect, useState } from "react";
import { Alert, ScrollView, StyleSheet, Text, View, Pressable } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { api } from "@/lib/api";
import { classifyRequestFailure, RequestFailure } from "@/lib/requestFailure";
import { Ionicons } from "@expo/vector-icons";
import { favoriteService } from "@/services/favoriteService";
import { ReportButton } from "@/components/ReportButton";
import { ErrorState, LoadingState } from "@/components/ScreenStates";

type Reading = { id: number; reading_date: string; feast?: string; saint_of_day?: string; liturgical_year: string; liturgical_season: string; liturgical_color: string; first_reading_reference: string; first_reading: string; responsorial_psalm_reference?: string; responsorial_psalm?: string; second_reading_reference?: string; second_reading?: string; gospel_reference: string; gospel: string; reflection?: string; prayer?: string };

/**
 * Reading detail.
 *
 * Accepts either `date` or `id` because both keys are used by callers:
 * `favorites.tsx` and `calendar.tsx` pass `date`, while `explore.tsx` passes
 * `id`. Previously only `date` was read, so navigating here with an `id` left
 * `date` undefined, the `if (date)` guard skipped the request entirely, and
 * `loading` was never cleared -- the screen showed a spinner forever.
 */
export default function ReadingDetail() {
  const { date, id } = useLocalSearchParams<{ date?: string; id?: string }>();
  const router = useRouter();
  const [reading, setReading] = useState<Reading | null>(null);
  const [loading, setLoading] = useState(true);
  const [failure, setFailure] = useState<RequestFailure | null>(null);
  const [missingParam, setMissingParam] = useState(false);
  const [isFavorited, setIsFavorited] = useState(false);
  const [favoriteId, setFavoriteId] = useState<number | null>(null);

  const load = useCallback(async () => {
    // Prefer the date form, which is what every caller that has one passes.
    const path = date
      ? `/api/readings/${date}`
      : id
        ? `/api/readings/id/${id}`
        : null;

    if (!path) {
      setMissingParam(true);
      setFailure(null);
      setReading(null);
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setFailure(null);
      const readingRes = await api.get<Reading>(path);
      setReading(readingRes.data);

      // Favourites are fetched separately and never fail this screen: the
      // endpoint requires a session, so pairing it in one `Promise.all` made a
      // signed-out visitor's successful response disappear.
      const favorites = await favoriteService.getFavoritesOptional();
      const favorite = favorites.find(
        (f) => f.resource_type === "reading" && f.target_resource_id === readingRes.data.id,
      );
      setIsFavorited(Boolean(favorite));
      setFavoriteId(favorite ? favorite.id : null);
    } catch (error: unknown) {
      setReading(null);
      setFailure(
        classifyRequestFailure(error, {
          fallbackNotFound: "That reading is not available.",
        }),
      );
    } finally {
      setLoading(false);
    }
  }, [date, id]);

  useEffect(() => {
    void Promise.resolve().then(() => load());
  }, [load]);

  async function toggleFavorite() {
    if (!reading) return;
    try {
      if (isFavorited && favoriteId) {
        await favoriteService.deleteFavorite(favoriteId);
        setIsFavorited(false);
        setFavoriteId(null);
      } else {
        const newFav = await favoriteService.createFavorite("reading", reading.id);
        setIsFavorited(true);
        setFavoriteId(newFav.id);
      }
    } catch {
      // The backend detail is more useful than a fixed string.
      Alert.alert("Could not update bookmark", "Please try again.");
    }
  }

  if (loading) {
    return <LoadingState label="Loading reading…" />;
  }

  // A request that never happened must never be reported as missing content.
  if (missingParam) {
    return (
      <View style={styles.center}>
        <ErrorState
          message="No reading was selected."
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

  if (!reading) {
    return (
      <View style={styles.center}>
        <ErrorState message="This reading could not be loaded." onRetry={() => void load()} />
      </View>
    );
  }

  const sections: [string, string | undefined, string | undefined][] = [
    ["First Reading", reading.first_reading_reference, reading.first_reading],
    ["Psalm", reading.responsorial_psalm_reference, reading.responsorial_psalm],
    ["Second Reading", reading.second_reading_reference, reading.second_reading],
    ["Gospel", reading.gospel_reference, reading.gospel],
  ];

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>{reading.feast || "Daily Reading"}</Text>
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
      <Text style={styles.date}>
        {reading.reading_date} · Year {reading.liturgical_year} ·{" "}
        {reading.liturgical_season} · {reading.liturgical_color}
      </Text>
      {reading.saint_of_day ? (
        <Text style={styles.meta}>Saint: {reading.saint_of_day}</Text>
      ) : null}
      {sections.map(([name, reference, content]) =>
        content ? (
          <View style={styles.section} key={name}>
            <Text style={styles.heading}>{name}</Text>
            {reference ? <Text style={styles.reference}>{reference}</Text> : null}
            <Text style={styles.content}>{content}</Text>
          </View>
        ) : null,
      )}
      {reading.reflection ? (
        <View style={styles.section}>
          <Text style={styles.heading}>Reflection</Text>
          <Text style={styles.content}>{reading.reflection}</Text>
        </View>
      ) : null}
      {reading.prayer ? (
        <View style={styles.section}>
          <Text style={styles.heading}>Prayer</Text>
          <Text style={styles.content}>{reading.prayer}</Text>
        </View>
      ) : null}
      <ReportButton resourceType="reading" resourceId={reading.id} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({ 
  container: { padding: 20, backgroundColor: "#fff" }, 
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  center: { flex: 1, justifyContent: "center", alignItems: "center", padding: 24 }, 
  title: { fontSize: 28, fontWeight: "800", color: "#0B6623" }, 
  date: { color: "#666", marginTop: 8 }, 
  meta: { color: "#0B6623", marginTop: 8, fontWeight: "700" }, 
  section: { marginTop: 22 }, 
  heading: { fontSize: 18, fontWeight: "800", color: "#222" }, 
  reference: { color: "#0B6623", marginTop: 4, fontWeight: "700" }, 
  content: { color: "#444", lineHeight: 23, marginTop: 9 } 
});