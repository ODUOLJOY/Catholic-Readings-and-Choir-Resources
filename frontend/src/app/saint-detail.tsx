import { useLocalSearchParams } from "expo-router";
import { View, Text, StyleSheet, ScrollView } from "react-native";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ActivityIndicator } from "react-native";
import { ReportButton } from "@/components/ReportButton";

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

  useEffect(() => {
    async function load() {
      try {
        const response = await api.get(`/api/saints/${id}`);
        setSaint(response.data);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    }
    if (id) load();
  }, [id]);

  if (loading) return <ActivityIndicator style={styles.center} color="#0B6623" />;
  if (!saint) return <Text style={styles.center}>Saint not found.</Text>;

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>{saint.name}</Text>
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
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  title: { fontSize: 28, fontWeight: "800", color: "#0B6623", marginBottom: 15 },
  meta: { fontSize: 16, color: "#666", marginBottom: 5 },
  biography: { fontSize: 16, color: "#333", marginTop: 20, lineHeight: 24 },
  description: { fontSize: 16, color: "#333", marginTop: 10, lineHeight: 24 }
});
