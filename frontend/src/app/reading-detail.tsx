import { useEffect, useState } from "react";
import { ActivityIndicator, Alert, ScrollView, StyleSheet, Text, View, Pressable } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { api } from "@/lib/api";
import { Ionicons } from "@expo/vector-icons";
import { favoriteService } from "@/services/favoriteService";
import { ReportButton } from "@/components/ReportButton";

type Reading = { id: number; reading_date: string; feast?: string; saint_of_day?: string; liturgical_year: string; liturgical_season: string; liturgical_color: string; first_reading_reference: string; first_reading: string; responsorial_psalm_reference?: string; responsorial_psalm?: string; second_reading_reference?: string; second_reading?: string; gospel_reference: string; gospel: string; reflection?: string; prayer?: string };

export default function ReadingDetail() {
  const { date } = useLocalSearchParams<{ date?: string }>();
  const [reading, setReading] = useState<Reading | null>(null);
  const [loading, setLoading] = useState(true);
  const [isFavorited, setIsFavorited] = useState(false);
  const [favoriteId, setFavoriteId] = useState<number | null>(null);

  useEffect(() => {
    if (date) void load();
  }, [date]);

  async function load() {
    try {
      setLoading(true);
      const [readingRes, favoritesRes] = await Promise.all([
        api.get<Reading>(`/api/readings/${date}`),
        favoriteService.getFavorites()
      ]);
      setReading(readingRes.data);
      
      const favorite = favoritesRes.find(f => f.resource_type === 'reading' && f.target_resource_id === readingRes.data.id);
      if (favorite) {
        setIsFavorited(true);
        setFavoriteId(favorite.id);
      }
    } catch (error: any) {
      Alert.alert("Reading unavailable", error?.response?.data?.detail || "Unable to load this reading.");
    } finally {
      setLoading(false);
    }
  }

  async function toggleFavorite() {
    if (!reading) return;
    try {
      if (isFavorited && favoriteId) {
        await favoriteService.deleteFavorite(favoriteId);
        setIsFavorited(false);
        setFavoriteId(null);
      } else {
        const newFav = await favoriteService.createFavorite('reading', reading.id);
        setIsFavorited(true);
        setFavoriteId(newFav.id);
      }
    } catch (error: any) {
      Alert.alert("Error", "Could not toggle favorite");
    }
  }

  if (loading) return <View style={styles.center}><ActivityIndicator color="#0B6623" /></View>;
  if (!reading) return <View style={styles.center}><Text>No reading selected.</Text></View>;

  const sections = [["First Reading", reading.first_reading_reference, reading.first_reading], ["Psalm", reading.responsorial_psalm_reference, reading.responsorial_psalm], ["Second Reading", reading.second_reading_reference, reading.second_reading], ["Gospel", reading.gospel_reference, reading.gospel]];

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>{reading.feast || "Daily Reading"}</Text>
        <Pressable onPress={toggleFavorite}>
          <Ionicons name={isFavorited ? "bookmark" : "bookmark-outline"} size={28} color="#0B6623" />
        </Pressable>
      </View>
      <Text style={styles.date}>{reading.reading_date} · Year {reading.liturgical_year} · {reading.liturgical_season} · {reading.liturgical_color}</Text>
      {reading.saint_of_day ? <Text style={styles.meta}>Saint: {reading.saint_of_day}</Text> : null}
      {sections.map(([name, reference, content]) => content ? <View style={styles.section} key={name}><Text style={styles.heading}>{name}</Text><Text style={styles.reference}>{reference}</Text><Text style={styles.content}>{content}</Text></View> : null)}
      {reading.reflection ? <View style={styles.section}><Text style={styles.heading}>Reflection</Text><Text style={styles.content}>{reading.reflection}</Text></View> : null}
      {reading.prayer ? <View style={styles.section}><Text style={styles.heading}>Prayer</Text><Text style={styles.content}>{reading.prayer}</Text></View> : null}
      <ReportButton resourceType="reading" resourceId={reading.id} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({ 
  container: { padding: 20, backgroundColor: "#fff" }, 
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  center: { flex: 1, justifyContent: "center", alignItems: "center" }, 
  title: { fontSize: 28, fontWeight: "800", color: "#0B6623" }, 
  date: { color: "#666", marginTop: 8 }, 
  meta: { color: "#0B6623", marginTop: 8, fontWeight: "700" }, 
  section: { marginTop: 22 }, 
  heading: { fontSize: 18, fontWeight: "800", color: "#222" }, 
  reference: { color: "#0B6623", marginTop: 4, fontWeight: "700" }, 
  content: { color: "#444", lineHeight: 23, marginTop: 9 } 
});
