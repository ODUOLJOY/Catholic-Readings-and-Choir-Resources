import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";
import { communityService, describeError, NotificationPreferences } from "@/services/communityService";

const initial: NotificationPreferences = {
  announcements: true,
  events: true,
  role_requests: true,
  messages: true,
};

export default function NotificationPreferencesScreen() {
  const [preferences, setPreferences] = useState(initial);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    communityService.getNotificationPreferences()
      .then(setPreferences)
      .catch((error) => Alert.alert("Preferences unavailable", describeError(error, "Could not load notification preferences.")))
      .finally(() => setLoading(false));
  }, []);

  async function save() {
    setSaving(true);
    try {
      setPreferences(await communityService.updateNotificationPreferences(preferences));
      Alert.alert("Saved", "In-app notification preferences were updated.");
    } catch (error) {
      Alert.alert("Save failed", describeError(error, "Please try again."));
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <View style={styles.center}><ActivityIndicator color="#0B6623" /></View>;

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Notification Preferences</Text>
      <Text style={styles.help}>These settings control supported in-app notifications. Push and email delivery are not enabled by these preferences alone.</Text>
      {([
        ["announcements", "Official announcements"],
        ["events", "Parish and diocesan events"],
        ["role_requests", "Role and membership requests"],
        ["messages", "Community messages"],
      ] as const).map(([key, label]) => (
        <View key={key} style={styles.row}>
          <Text style={styles.label}>{label}</Text>
          <Switch
            value={preferences[key]}
            onValueChange={(value) => setPreferences((current) => ({ ...current, [key]: value }))}
            trackColor={{ true: "#0B6623" }}
          />
        </View>
      ))}
      <Pressable style={styles.button} onPress={save} disabled={saving}>
        <Text style={styles.buttonText}>{saving ? "Saving..." : "Save preferences"}</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#F7F9F7" },
  content: { padding: 20 },
  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  title: { fontSize: 25, fontWeight: "800", color: "#0B6623" },
  help: { color: "#59665C", lineHeight: 21, marginTop: 8, marginBottom: 18 },
  row: { backgroundColor: "#fff", padding: 14, borderRadius: 10, marginBottom: 8, flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  label: { color: "#26382B", fontWeight: "600" },
  button: { backgroundColor: "#0B6623", padding: 14, borderRadius: 10, alignItems: "center", marginTop: 12 },
  buttonText: { color: "#fff", fontWeight: "700" },
});
