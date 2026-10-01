import { useEffect, useState } from "react";
import { ScrollView, StyleSheet, Text, View, ActivityIndicator } from "react-native";
import { api } from "@/lib/api";

export default function DirectoryManagement() {
  const [jurisdictions, setJurisdictions] = useState([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get("/api/v1/locations/dioceses?country=KE"),
      api.get("/api/v1/locations/admin/stats")
    ]).then(([jRes, sRes]) => {
      setJurisdictions(jRes.data);
      setStats(sRes.data);
      setLoading(false);
    });
  }, []);

  if (loading) return <ActivityIndicator style={styles.loader} />;

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>Catholic Directory Management</Text>
      
      {stats && (
        <View style={styles.card}>
          <Text style={styles.subtitle}>Dashboard</Text>
          <Text>Total Jurisdictions: {stats.total_jurisdictions} (Archdioceses: {stats.archdioceses}, Dioceses: {stats.dioceses}, Mil. Ord.: {stats.military_ordinariate})</Text>
          <Text>Total Deaneries: {stats.total_deaneries}</Text>
          <Text>Total Parishes: {stats.total_parishes} (Verified: {stats.verified_parishes}, Review: {stats.needs_review_parishes})</Text>
        </View>
      )}

      <View style={styles.menu}>
        <Text style={styles.subtitle}>Management</Text>
        <Text style={styles.menuItem}>Manage Deaneries</Text>
        <Text style={styles.menuItem}>Manage Parishes</Text>
        <Text style={styles.menuItem}>Bulk Import</Text>
        <Text style={styles.menuItem}>Parish Requests</Text>
      </View>

      <Text style={styles.subtitle}>Jurisdictions</Text>
      {jurisdictions.map((j: any) => (
        <View key={j.id} style={styles.card}>
          <Text style={styles.name}>{j.name}</Text>
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 20, backgroundColor: "#F7F9F7" },
  title: { fontSize: 24, fontWeight: "bold", marginBottom: 20 },
  subtitle: { fontSize: 18, fontWeight: "600", marginBottom: 10 },
  card: { padding: 15, backgroundColor: "#fff", marginBottom: 10, borderRadius: 8, borderWidth: 1, borderColor: "#E5EAE6" },
  name: { fontSize: 18, fontWeight: "bold" },
  menu: { marginTop: 20, marginBottom: 20, backgroundColor: "#fff", padding: 15, borderRadius: 8 },
  menuItem: { fontSize: 16, color: "#2E7D32", marginBottom: 5 },
  loader: { marginTop: 50 },
});
