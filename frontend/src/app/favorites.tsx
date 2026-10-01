import { useEffect, useState } from "react";
import { ActivityIndicator, FlatList, StyleSheet, Text, View, Pressable, Alert } from "react-native";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { api } from "@/lib/api";
import { favoriteService, Favorite } from "@/services/favoriteService";

export default function Favorites() {
  const [resources, setResources] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  async function loadFavorites() {
    setLoading(true);
    try {
      const favs = await favoriteService.getFavorites();
      
      const resourcesPromises = favs.map(async (fav) => {
        let endpoint = "";
        if (fav.resource_type === 'reading') endpoint = `/api/readings/id/${fav.target_resource_id}`;
        else if (fav.resource_type === 'saint') endpoint = `/api/saints/${fav.target_resource_id}`;
        else if (fav.resource_type === 'choir') endpoint = `/api/choir/${fav.target_resource_id}`;
        
        if (!endpoint) return null;
        
        try {
            const res = await api.get(endpoint);
            return { ...res.data, favorite_id: fav.id, type: fav.resource_type };
        } catch {
            return null;
        }
      });
      
      const res = await Promise.all(resourcesPromises);
      setResources(res.filter(r => r !== null));
    } catch (error) {
      Alert.alert("Error", "Failed to load favorites");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void Promise.resolve().then(loadFavorites);
  }, []);

  async function removeFavorite(favId: number) {
    try {
      await favoriteService.deleteFavorite(favId);
      setResources(resources.filter(r => r.favorite_id !== favId));
    } catch (error: any) {
      Alert.alert("Error", "Failed to remove favorite");
    }
  }

  function openResource(item: any) {
    if (item.type === 'reading') {
      router.push({ pathname: "/reading-detail", params: { date: item.reading_date } });
    } else if (item.type === 'saint') {
      router.push({ pathname: "/(tabs)/admin/saints", params: { id: item.id } });
    } else if (item.type === 'choir') {
      router.push({ pathname: "/(tabs)/choir", params: { id: item.id } });
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Favorites</Text>
      {loading ? <ActivityIndicator color="#0B6623" /> : 
        <FlatList 
          data={resources}
          keyExtractor={(item) => `${item.type}-${item.id}`}
          renderItem={({ item }) => (
            <View style={styles.card}>
              <Pressable onPress={() => openResource(item)} style={styles.cardContent}>
                <Text style={styles.name}>{item.title || item.name}</Text>
                <Text style={styles.type}>{item.type.toUpperCase()}</Text>
              </Pressable>
              <Pressable onPress={() => removeFavorite(item.favorite_id)}>
                <Ionicons name="trash" size={24} color="#C62828" />
              </Pressable>
            </View>
          )}
          ListEmptyComponent={<Text style={styles.empty}>No saved resources yet.</Text>}
        />
      }
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 18, backgroundColor: "#fff" },
  title: { fontSize: 28, fontWeight: "800", color: "#0B6623", marginBottom: 14 },
  card: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderWidth: 1, borderColor: "#e5e5e5", borderRadius: 12, padding: 15, marginBottom: 10 },
  cardContent: { flex: 1 },
  name: { fontSize: 18, fontWeight: "800" },
  type: { color: "#666", marginTop: 5 },
  empty: { textAlign: "center", color: "#777", marginTop: 40 }
});
