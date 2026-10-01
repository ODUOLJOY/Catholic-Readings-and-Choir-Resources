import { useEffect, useState } from "react";
import { View, Text, StyleSheet, FlatList, ActivityIndicator, Alert } from "react-native";
import { api } from "../../lib/api";

export default function ManageDeaneries() {
  const [deaneries, setDeaneries] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDeaneries();
  }, []);

  const fetchDeaneries = async () => {
    try {
      // Need a way to fetch all deaneries, similar to parishes. 
      // I'll add an endpoint for this.
      const res = await api.get("/api/v1/locations/deaneries");
      setDeaneries(res.data);
    } catch (e) {
      Alert.alert("Error", "Failed to load deaneries");
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Manage Deaneries</Text>
      <FlatList
        data={deaneries}
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
