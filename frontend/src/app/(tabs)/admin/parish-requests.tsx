import { useEffect, useState } from "react";
import { View, Text, StyleSheet, FlatList, TouchableOpacity, ActivityIndicator, Alert } from "react-native";
import { api } from "@/lib/api";

export default function ParishRequests() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchRequests();
  }, []);

  const fetchRequests = async () => {
    try {
      const res = await api.get("/api/v1/parish-requests");
      setRequests(res.data);
    } catch (e) {
      Alert.alert("Error", "Failed to load requests");
    } finally {
      setLoading(false);
    }
  };

  const updateStatus = async (id: number, status: string) => {
    try {
      await api.put(`/api/v1/parish-requests/${id}/status?status=${status}`);
      fetchRequests();
    } catch (e) {
      Alert.alert("Error", "Failed to update status");
    }
  };

  if (loading) return <ActivityIndicator />;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Parish Requests</Text>
      <FlatList
        data={requests}
        keyExtractor={(item: any) => item.id.toString()}
        renderItem={({ item }: any) => (
          <View style={styles.card}>
            <Text style={styles.name}>{item.parish_name}</Text>
            <Text>Status: {item.status}</Text>
            <Text>Town: {item.town}</Text>
            {item.status === 'pending' && (
              <View style={styles.actions}>
                <TouchableOpacity onPress={() => updateStatus(item.id, 'approved')} style={styles.button}>
                  <Text style={styles.buttonText}>Approve</Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={() => updateStatus(item.id, 'rejected')} style={[styles.button, styles.buttonRed]}>
                  <Text style={styles.buttonText}>Reject</Text>
                </TouchableOpacity>
              </View>
            )}
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
  actions: { flexDirection: 'row', marginTop: 10 },
  button: { backgroundColor: '#2E7D32', padding: 8, borderRadius: 5, marginRight: 10 },
  buttonRed: { backgroundColor: '#C62828' },
  buttonText: { color: '#fff' }
});
