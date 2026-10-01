import { useEffect, useState } from "react";
import { ActivityIndicator, Alert, ScrollView, StyleSheet, Text, View } from "react-native";
import { api } from "@/lib/api";

type AuditRecord = {
  id: number;
  actor_id: number | null;
  actor_type: string;
  action: string;
  target_type: string;
  target_id: number | null;
  scope_type: string | null;
  scope_id: number | null;
  reason: string | null;
  created_at: string;
};

export default function CommunityAuditScreen() {
  const [records, setRecords] = useState<AuditRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<AuditRecord[]>("/api/community/audit")
      .then((response) => setRecords(response.data))
      .catch((error) => Alert.alert("Audit log unavailable", error?.response?.data?.detail ?? "Check administrator scope."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <View style={styles.center}><ActivityIndicator color="#0B6623" /></View>;
  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Administrative Audit Log</Text>
      {records.length === 0 ? <Text style={styles.body}>No audit actions are available in your authorized scope.</Text> : records.map((record) => (
        <View key={record.id} style={styles.card}>
          <Text style={styles.action}>{record.action}</Text>
          <Text style={styles.body}>{record.target_type} #{record.target_id ?? "—"} · {record.scope_type ?? "global"} #{record.scope_id ?? "—"}</Text>
          <Text style={styles.meta}>{record.actor_type} #{record.actor_id ?? "system"} · {new Date(record.created_at).toLocaleString()}</Text>
          {record.reason ? <Text style={styles.body}>{record.reason}</Text> : null}
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#F7F9F7" },
  content: { padding: 20 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  title: { fontSize: 24, color: "#0B6623", fontWeight: "800", marginBottom: 14 },
  card: { backgroundColor: "#fff", padding: 13, borderRadius: 10, marginBottom: 8 },
  action: { color: "#163C23", fontWeight: "700" },
  body: { color: "#444", marginTop: 5 },
  meta: { color: "#7A847D", fontSize: 12, marginTop: 6 },
});
