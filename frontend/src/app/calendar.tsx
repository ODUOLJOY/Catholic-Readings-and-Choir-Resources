import { useEffect, useState } from "react";
import { ActivityIndicator, FlatList, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { router } from "expo-router";
import { api } from "@/lib/api";

type CalendarDay = {
  date: string;
  celebration: string;
  rank: string;
  color: string;
  season: string;
};

export default function Calendar() {
  const [items, setItems] = useState<CalendarDay[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void load();
  }, []);

  async function load() {
    try {
      setLoading(true);
      // For demonstration, load the current month.
      const today = new Date();
      const firstDay = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split('T')[0];
      const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().split('T')[0];
      
      const response = await api.get("/api/v1/liturgy/calendar", { 
        params: { start_date: firstDay, end_date: lastDay } 
      });
      setItems(response.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Liturgical Calendar</Text>
      {loading ? (
        <ActivityIndicator color="#0B6623" />
      ) : (
        <FlatList
          data={items}
          keyExtractor={(item) => item.date}
          renderItem={({ item }) => (
            <TouchableOpacity 
              style={styles.card} 
              onPress={() => router.push({ pathname: "/readings", params: { date: item.date } })}
            >
              <Text style={styles.date}>{item.date}</Text>
              <Text style={styles.celebration}>{item.celebration}</Text>
              <Text style={styles.meta}>{item.rank} · {item.season} · {item.color}</Text>
            </TouchableOpacity>
          )}
          ListEmptyComponent={<Text style={styles.empty}>No calendar data available.</Text>}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 18, backgroundColor: "#fff" },
  title: { fontSize: 28, fontWeight: "800", color: "#0B6623", marginBottom: 14 },
  card: { padding: 15, borderWidth: 1, borderColor: "#e5e5e5", borderRadius: 12, marginBottom: 10 },
  date: { color: "#0B6623", fontWeight: "800" },
  celebration: { fontSize: 17, fontWeight: "700", marginTop: 4 },
  meta: { color: "#666", marginTop: 5 },
  empty: { textAlign: "center", color: "#777", marginTop: 40 }
});
