import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, FlatList, RefreshControl, StyleSheet, Text, TextInput, View, Pressable, Alert } from "react-native";
import { router } from "expo-router";
import { api } from "@/lib/api";
import { requestErrorMessage } from "@/lib/requestFailure";
import { Ionicons } from "@expo/vector-icons";
import { favoriteService, Favorite } from "@/services/favoriteService";
import { ErrorState } from "@/components/ScreenStates";

type Saint = { id: number; name: string; feast_date?: string; country?: string; patronage?: string; short_description?: string };

export default function Saints() { 
  const [items, setItems] = useState<Saint[]>([]); 
  const [query, setQuery] = useState(""); 
  const [loading, setLoading] = useState(true); 
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [favorites, setFavorites] = useState<Favorite[]>([]);

  const load = useCallback(async (value = query) => { 
    try { 
      setLoading(true);
      setError(null);
      // Favourites are fetched separately and cannot fail this screen.
      // `/api/favorites` needs a session, so pairing it in one `Promise.all`
      // meant a signed-out visitor's 401 discarded the saints response beside it
      // and the screen claimed "No saints found."
      const saintsRes = value.trim()
        ? await api.get(`/api/saints/search/${encodeURIComponent(value.trim())}`)
        : await api.get("/api/saints/");
      setItems(Array.isArray(saintsRes.data) ? saintsRes.data : []); 
      setFavorites(await favoriteService.getFavoritesOptional());
    } catch (requestError: unknown) {
      // Previously there was no `catch` at all, so the rejection was unhandled
      // and the screen rendered its empty copy for a server it never reached.
      setItems([]);
      setError(requestErrorMessage(requestError, "Could not load saints."));
    } finally { 
      setLoading(false); 
      setRefreshing(false);
    } 
  }, [query]);

  useEffect(() => { 
    void Promise.resolve().then(() => load("")); 
    // Loads once on mount; the search field drives later loads explicitly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); 

  async function onRefresh() {
    setRefreshing(true);
    await load();
  }

  async function toggleFavorite(saint: Saint) {
    const isFavorited = favorites.some(f => f.resource_type === 'saint' && f.target_resource_id === saint.id);
    const favorite = favorites.find(f => f.resource_type === 'saint' && f.target_resource_id === saint.id);
    
    try {
      if (isFavorited && favorite) {
        await favoriteService.deleteFavorite(favorite.id);
        setFavorites(favorites.filter(f => f.id !== favorite.id));
      } else {
        const newFav = await favoriteService.createFavorite('saint', saint.id);
        setFavorites([...favorites, newFav]);
      }
    } catch {
      Alert.alert("Error", "Could not toggle favorite");
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Saints</Text>
      <TextInput
        style={styles.input}
        placeholder="Search saints"
        value={query}
        onChangeText={setQuery}
        onSubmitEditing={() => void load()}
        returnKeyType="search"
        accessibilityLabel="Search saints"
      />
      {loading ? <ActivityIndicator color="#0B6623" /> : 
        <FlatList 
          data={items} 
          keyExtractor={(item) => String(item.id)} 
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => void onRefresh()}
              tintColor="#0B6623"
            />
          }
          renderItem={({ item }) => {
            const isFavorited = favorites.some(f => f.resource_type === 'saint' && f.target_resource_id === item.id);
            return (
              <Pressable onPress={() => router.push({ pathname: "/saint-detail", params: { id: item.id.toString() } })}>
              <View style={styles.card}>
                <View style={styles.cardHeader}>
                  <Text style={styles.name}>{item.name}</Text>
                  <Pressable onPress={() => void toggleFavorite(item)} accessibilityRole="button">
                    <Ionicons name={isFavorited ? "bookmark" : "bookmark-outline"} size={24} color="#0B6623" />
                  </Pressable>
                </View>
                {item.feast_date ? <Text style={styles.meta}>Feast: {item.feast_date}</Text> : null}
                {item.country ? <Text style={styles.meta}>{item.country}</Text> : null}
                {item.patronage ? <Text style={styles.meta}>Patron of {item.patronage}</Text> : null}
                {item.short_description ? <Text style={styles.description}>{item.short_description}</Text> : null}
              </View>
            </Pressable>
            );
          }} 
          ListEmptyComponent={
            error ? (
              <ErrorState message={error} onRetry={() => void load()} />
            ) : (
              <Text style={styles.empty}>
                {query.trim() ? "No saints match that search." : "No saints available yet."}
              </Text>
            )
          }
        />
      }
    </View>
  ); 
}

const styles = StyleSheet.create({ 
  container: { flex: 1, padding: 18, backgroundColor: "#fff" }, 
  title: { fontSize: 28, fontWeight: "800", color: "#0B6623", marginBottom: 14 }, 
  input: { borderWidth: 1, borderColor: "#ddd", borderRadius: 10, padding: 12, marginBottom: 14 }, 
  card: { borderWidth: 1, borderColor: "#e5e5e5", borderRadius: 12, padding: 15, marginBottom: 10 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  name: { fontSize: 18, fontWeight: "800" }, 
  meta: { color: "#666", marginTop: 5 }, 
  description: { color: "#444", marginTop: 8 }, 
  empty: { textAlign: "center", color: "#777", marginTop: 40 } 
});
