import { useEffect, useState } from "react";
import { View, Text, StyleSheet, FlatList, TouchableOpacity, ActivityIndicator, Alert, TextInput } from "react-native";
import { api } from "@/lib/api";

export default function ManageParishes() {
  const [parishes, setParishes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");

  const fetchParishes = async () => {
    try {
      const res = await api.get("/api/v1/locations/parishes");
      setParishes(res.data);
    } catch (e) {
      Alert.alert("Error", "Failed to load parishes");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void Promise.resolve().then(fetchParishes);
  }, []);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Manage Parishes</Text>
      <FlatList
        data={parishes}
        keyExtractor={(item: any) => item.id.toString()}
        renderItem={({ item }: any) => (
          <View style={styles.card}>
            <Text style={styles.name}>{item.name}</Text>
            <Text>Status: {item.verification_status}</Text>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 20 },
  title: { fontSize: 24, fontWeight: "bold", marginBottom: 20 },
  card: { padding: 15, backgroundColor: "#fff", marginBottom: 10, borderRadius: 8, borderWidth: 1, borderColor: "#E5EAE6" },
  name: { fontSize: 18, fontWeight: "bold" },
});
