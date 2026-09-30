import { useEffect, useState } from "react";
import { ActivityIndicator, Alert, FlatList, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { api } from "@/lib/api";

type Reading = { id: number; reading_date: string; feast?: string; liturgical_season: string; published: boolean; first_reading_reference: string; first_reading: string; gospel_reference: string; gospel: string };

export default function ReadingManagement() {
  const [items, setItems] = useState<Reading[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Reading | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => { void load(); }, []);

  async function load() {
    try {
      setLoading(true);
      const response = await api.get("/api/readings/", { params: { page: 1, limit: 100 } });
      setItems(response.data?.items || []);
    } catch (error: any) {
      Alert.alert("Readings unavailable", error?.response?.data?.detail || "Unable to load readings.");
    } finally { setLoading(false); }
  }

  async function update(id: number, action: "publish" | "unpublish" | "delete") {
    try {
      if (action === "delete") await api.delete(`/api/readings/${id}`);
      else await api.post(`/api/readings/${id}/${action}`);
      await load();
    } catch (error: any) {
      Alert.alert("Action failed", error?.response?.data?.detail || "Unable to update this reading.");
    }
  }

  async function saveEdit() {
    if (!editing) return;
    try {
      setSaving(true);
      await api.put(`/api/readings/${editing.id}`, {
        feast: editing.feast || null,
        liturgical_season: editing.liturgical_season,
        first_reading_reference: editing.first_reading_reference,
        first_reading: editing.first_reading,
        gospel_reference: editing.gospel_reference,
        gospel: editing.gospel,
      });
      setEditing(null);
      await load();
    } catch (error: any) {
      Alert.alert("Save failed", error?.response?.data?.detail || "Unable to update this reading.");
    } finally { setSaving(false); }
  }

  if (loading) return <View style={styles.center}><ActivityIndicator color="#0B6623" /></View>;
  if (editing) return <View style={styles.container}><Text style={styles.title}>Edit Reading</Text><TextInput style={styles.input} value={editing.feast || ""} placeholder="Feast" onChangeText={(value) => setEditing({ ...editing, feast: value })} /><TextInput style={styles.input} value={editing.liturgical_season} placeholder="Season" onChangeText={(value) => setEditing({ ...editing, liturgical_season: value })} /><TextInput style={styles.input} value={editing.first_reading_reference} placeholder="First reading reference" onChangeText={(value) => setEditing({ ...editing, first_reading_reference: value })} /><TextInput style={styles.area} value={editing.first_reading} multiline placeholder="First reading" onChangeText={(value) => setEditing({ ...editing, first_reading: value })} /><TextInput style={styles.input} value={editing.gospel_reference} placeholder="Gospel reference" onChangeText={(value) => setEditing({ ...editing, gospel_reference: value })} /><TextInput style={styles.area} value={editing.gospel} multiline placeholder="Gospel" onChangeText={(value) => setEditing({ ...editing, gospel: value })} /><Pressable style={styles.button} onPress={saveEdit} disabled={saving}><Text style={styles.buttonText}>{saving ? "Saving..." : "Save Changes"}</Text></Pressable><Pressable onPress={() => setEditing(null)}><Text style={styles.cancel}>Cancel</Text></Pressable></View>;

  return <View style={styles.container}><Text style={styles.title}>Manage Readings</Text><FlatList data={items} keyExtractor={(item) => String(item.id)} renderItem={({ item }) => <View style={styles.card}><Text style={styles.heading}>{item.reading_date}</Text><Text style={styles.feast}>{item.feast || "Daily Reading"}</Text><Text style={styles.meta}>{item.liturgical_season} · {item.published ? "Published" : "Draft"}</Text><View style={styles.actions}><Pressable onPress={() => setEditing(item)}><Text style={styles.action}>Edit</Text></Pressable><Pressable onPress={() => update(item.id, item.published ? "unpublish" : "publish")}><Text style={styles.action}>{item.published ? "Unpublish" : "Publish"}</Text></Pressable><Pressable onPress={() => update(item.id, "delete")}><Text style={styles.danger}>Delete</Text></Pressable></View></View>} ListEmptyComponent={<Text style={styles.empty}>No published readings found.</Text>} /></View>;
}

const styles = StyleSheet.create({ container: { flex: 1, padding: 18, backgroundColor: "#fff" }, center: { flex: 1, alignItems: "center", justifyContent: "center" }, title: { fontSize: 28, fontWeight: "800", color: "#0B6623", marginBottom: 15 }, card: { borderWidth: 1, borderColor: "#e5e5e5", borderRadius: 12, padding: 15, marginBottom: 10 }, heading: { color: "#0B6623", fontWeight: "800" }, feast: { fontSize: 17, fontWeight: "700", marginTop: 4 }, meta: { color: "#666", marginTop: 5 }, actions: { flexDirection: "row", gap: 18, marginTop: 12 }, action: { color: "#0B6623", fontWeight: "800" }, danger: { color: "#C62828", fontWeight: "800" }, input: { borderWidth: 1, borderColor: "#ddd", borderRadius: 9, padding: 12, marginBottom: 10 }, area: { borderWidth: 1, borderColor: "#ddd", borderRadius: 9, padding: 12, minHeight: 100, marginBottom: 10, textAlignVertical: "top" }, button: { backgroundColor: "#0B6623", borderRadius: 9, padding: 14, alignItems: "center" }, buttonText: { color: "#fff", fontWeight: "800" }, cancel: { textAlign: "center", color: "#0B6623", marginTop: 16, fontWeight: "700" }, empty: { textAlign: "center", color: "#777", marginTop: 40 } });
