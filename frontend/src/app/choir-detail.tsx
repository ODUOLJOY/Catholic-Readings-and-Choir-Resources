import { useEffect, useState } from "react";
import { ActivityIndicator, Alert, ScrollView, StyleSheet, Text, View, Pressable, Linking } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { api } from "@/lib/api";
import { Ionicons } from "@expo/vector-icons";
import { favoriteService } from "@/services/favoriteService";
import { ReportButton } from "@/components/ReportButton";

export default function ChoirDetail() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const [resource, setResource] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [isFavorited, setIsFavorited] = useState(false);
  const [favoriteId, setFavoriteId] = useState<number | null>(null);

  useEffect(() => {
    if (id) void load();
  }, [id]);

  async function load() {
    try {
      setLoading(true);
      const [res, favoritesRes] = await Promise.all([
        api.get(`/api/v1/choir/${id}`),
        favoriteService.getFavorites()
      ]);
      setResource(res.data);
      
      const favorite = favoritesRes.find(f => f.resource_type === 'choir' && f.target_resource_id === parseInt(id!));
      if (favorite) {
        setIsFavorited(true);
        setFavoriteId(favorite.id);
      }
    } catch (error: any) {
      Alert.alert("Resource unavailable", "Unable to load this choir resource.");
    } finally {
      setLoading(false);
    }
  }

  async function toggleFavorite() {
    if (!resource) return;
    try {
      if (isFavorited && favoriteId) {
        await favoriteService.deleteFavorite(favoriteId);
        setIsFavorited(false);
        setFavoriteId(null);
      } else {
        const newFav = await favoriteService.createFavorite('choir', resource.id);
        setIsFavorited(true);
        setFavoriteId(newFav.id);
      }
    } catch (error: any) {
      Alert.alert("Error", "Could not toggle favorite");
    }
  }

  if (loading) return <View style={styles.center}><ActivityIndicator color="#0B6623" /></View>;
  if (!resource) return <View style={styles.center}><Text>No resource selected.</Text></View>;

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>{resource.title}</Text>
        <Pressable onPress={toggleFavorite}>
          <Ionicons name={isFavorited ? "bookmark" : "bookmark-outline"} size={28} color="#0B6623" />
        </Pressable>
      </View>
      <Text style={styles.meta}>{resource.category} · {resource.file_type}</Text>
      <Text style={styles.content}>{resource.description}</Text>
      
      <Pressable style={styles.button} onPress={() => Linking.openURL(resource.file_url)}>
        <Text style={styles.buttonText}>Open Resource</Text>
      </Pressable>

      <ReportButton resourceType="choir" resourceId={resource.id} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({ 
  container: { padding: 20, backgroundColor: "#fff" }, 
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  center: { flex: 1, justifyContent: "center", alignItems: "center" }, 
  title: { fontSize: 28, fontWeight: "800", color: "#0B6623" }, 
  meta: { color: "#666", marginTop: 8, fontWeight: "700" }, 
  content: { color: "#444", lineHeight: 23, marginTop: 15 },
  button: { marginTop: 20, backgroundColor: '#0B6623', padding: 15, borderRadius: 8, alignItems: 'center' },
  buttonText: { color: '#fff', fontWeight: 'bold' }
});
