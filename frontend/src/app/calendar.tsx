import { useCallback, useEffect, useState } from "react";
import { FlatList, RefreshControl, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { api } from "@/lib/api";
import { requestErrorMessage } from "@/lib/requestFailure";
import { kenyaMonthKey, kenyaMonthLabel, kenyaMonthRange, shiftKenyaMonth } from "@/utils/calendar";
import { ErrorState, LoadingState } from "@/components/ScreenStates";

type CalendarDay = {
  date: string;
  celebration: string;
  rank: string;
  color: string;
  season: string;
};

export default function Calendar() {
  const [monthKey, setMonthKey] = useState(() => kenyaMonthKey());
  const [items, setItems] = useState<CalendarDay[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isCurrentMonth = monthKey === kenyaMonthKey();

  const load = useCallback(async (targetMonth: string) => {
    try {
      setLoading(true);
      setError(null);
      // `kenyaMonthRange` accepts a `Date`, but the screen navigates by month key,
      // so the key is turned back into a UTC-noon `Date`. The resulting range is
      // the first and last day of that Nairobi month, which is what the backend's
      // `start_date`/`end_date` parameters already expect.
      const [year, month] = targetMonth.split("-").map(Number);
      const { startDate, endDate } = kenyaMonthRange(
        new Date(Date.UTC(year, month - 1, 1, 12)),
      );

      const response = await api.get("/api/v1/liturgy/calendar", {
        params: { start_date: startDate, end_date: endDate },
      });
      setItems(Array.isArray(response.data) ? response.data : []);
    } catch (requestError: unknown) {
      // The previous handler only logged to the console, so the member saw
      // "No calendar data available." and could not tell an outage from an empty
      // month, and had no way to retry.
      setItems([]);
      setError(requestErrorMessage(requestError, "Could not load the liturgical calendar."));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(() => load(monthKey));
  }, [load, monthKey]);

  function changeMonth(delta: number) {
    setMonthKey((current) => shiftKenyaMonth(current, delta));
  }

  async function onRefresh() {
    setRefreshing(true);
    await load(monthKey);
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Liturgical Calendar</Text>
        <TouchableOpacity
          style={styles.refreshButton}
          onPress={() => void onRefresh()}
          accessibilityRole="button"
          accessibilityLabel="Refresh calendar"
        >
          <Ionicons name="refresh" size={22} color="#0B6623" />
        </TouchableOpacity>
      </View>

      <View style={styles.monthNav}>
        <TouchableOpacity
          style={styles.monthButton}
          onPress={() => changeMonth(-1)}
          accessibilityRole="button"
          accessibilityLabel="Previous month"
        >
          <Ionicons name="chevron-back" size={24} color="#0B6623" />
        </TouchableOpacity>

        <Text style={styles.monthLabel}>{kenyaMonthLabel(monthKey)}</Text>

        <TouchableOpacity
          style={styles.monthButton}
          onPress={() => changeMonth(1)}
          accessibilityRole="button"
          accessibilityLabel="Next month"
        >
          <Ionicons name="chevron-forward" size={24} color="#0B6623" />
        </TouchableOpacity>
      </View>

      {!isCurrentMonth ? (
        <TouchableOpacity
          style={styles.todayButton}
          onPress={() => setMonthKey(kenyaMonthKey())}
          accessibilityRole="button"
        >
          <Text style={styles.todayText}>Back to this month</Text>
        </TouchableOpacity>
      ) : null}

      {loading ? (
        <LoadingState label="Loading calendar…" />
      ) : (
        <FlatList
          data={items}
          keyExtractor={(item) => item.date}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => void onRefresh()}
              tintColor="#0B6623"
            />
          }
          renderItem={({ item }) => (
            <TouchableOpacity
              style={styles.card}
              onPress={() => router.push({ pathname: "/(tabs)/readings", params: { date: item.date } })}
            >
              <Text style={styles.date}>{item.date}</Text>
              <Text style={styles.celebration}>{item.celebration}</Text>
              <Text style={styles.meta}>{item.rank} · {item.season} · {item.color}</Text>
            </TouchableOpacity>
          )}
          ListEmptyComponent={
            error ? (
              <ErrorState message={error} onRetry={() => void load(monthKey)} />
            ) : (
              <Text style={styles.empty}>No calendar data available.</Text>
            )
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 18, backgroundColor: "#fff" },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  title: { fontSize: 28, fontWeight: "800", color: "#0B6623", marginBottom: 14 },
  refreshButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "#EAF4ED",
    alignItems: "center",
    justifyContent: "center",
  },
  monthNav: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: "#F7F9F7",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#E5EAE6",
    padding: 8,
    marginBottom: 12,
  },
  monthButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "#EAF4ED",
    alignItems: "center",
    justifyContent: "center",
  },
  monthLabel: { flex: 1, textAlign: "center", fontSize: 16, fontWeight: "700", color: "#0B6623" },
  todayButton: { alignSelf: "center", marginBottom: 12 },
  todayText: { color: "#0B6623", fontWeight: "700", fontSize: 14 },
  card: { padding: 15, borderWidth: 1, borderColor: "#e5e5e5", borderRadius: 12, marginBottom: 10 },
  date: { color: "#0B6623", fontWeight: "800" },
  celebration: { fontSize: 17, fontWeight: "700", marginTop: 4 },
  meta: { color: "#666", marginTop: 5 },
  empty: { textAlign: "center", color: "#777", marginTop: 40 }
});