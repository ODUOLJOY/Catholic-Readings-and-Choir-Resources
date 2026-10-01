import { View, Text, StyleSheet, ScrollView, Pressable } from "react-native";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ActivityIndicator } from "react-native";
import { ReportButton } from "@/components/ReportButton";
import { favoriteService } from "@/services/favoriteService";
import { Ionicons } from "@expo/vector-icons";

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
  const [saint, setSaint] = useState<Saint | null>(null);
  const [loading, setLoading] = useState(true);
  const [isFavorited, setIsFavorited] = useState(false);
  const [favoriteId, setFavoriteId] = useState<number | null>(null);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const [res, favoritesRes] = await Promise.all([
          api.get(`/api/saints/${id}`),
          favoriteService.getFavorites()
        ]);
        setSaint(res.data);
        
        const favorite = favoritesRes.find(f => f.resource_type === 'saint' && f.target_resource_id === parseInt(id!));
        if (favorite) {
          setIsFavorited(true);
          setFavoriteId(favorite.id);
        }
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    }
    if (id) load();
  }, [id]);

  async function toggleFavorite() {
    if (!saint) return;
    try {
      if (isFavorited && favoriteId) {
        await favoriteService.deleteFavorite(favoriteId);
        setIsFavorited(false);
        setFavoriteId(null);
      } else {
        const newFav = await favoriteService.createFavorite('saint', saint.id);
        setIsFavorited(true);
        setFavoriteId(newFav.id);
      }
    } catch (error: any) {
      console.error("Could not toggle favorite", error);
    }
  }

  if (loading) return <ActivityIndicator style={styles.center} color="#0B6623" />;
  if (!saint) return <Text style={styles.center}>Saint not found.</Text>;

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>{saint.name}</Text>
        <Pressable onPress={toggleFavorite}>
          <Ionicons name={isFavorited ? "bookmark" : "bookmark-outline"} size={28} color="#0B6623" />
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
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  title: { fontSize: 28, fontWeight: "800", color: "#0B6623" },
  meta: { fontSize: 16, color: "#666", marginBottom: 5 },
  biography: { fontSize: 16, color: "#333", marginTop: 20, lineHeight: 24 },
  description: { fontSize: 16, color: "#333", marginTop: 10, lineHeight: 24 }
});
