import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useLocalSearchParams } from "expo-router";
import { api } from "@/lib/api";

type MembershipRequest = {
  id: number;
  user_id: number;
  full_name: string;
  email: string;
  parish_id: number;
  parish_name: string;
  status: string;
  requested_at: string;
};

type Assignment = {
  assignment_id: number;
  user_id: number;
  full_name: string;
  email: string;
  role: string;
  scope_type: string;
  scope_id: number | null;
};

type Suggestion = {
  id: number;
  category: string;
  body: string;
  scope_type: string;
  scope_id: number;
  status: string;
  is_anonymous: boolean;
};

export default function CommunityAdminScreen() {
  const { section } = useLocalSearchParams<{ section?: string }>();
  const [memberships, setMemberships] = useState<MembershipRequest[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      if (section === "administrators") {
        const response = await api.get<Assignment[]>("/api/community/administrators");
        setAssignments(response.data);
      } else if (section === "suggestions") {
        const response = await api.get<Suggestion[]>("/api/community/suggestions/review");
        setSuggestions(response.data);
      } else {
        const response = await api.get<MembershipRequest[]>("/api/community/memberships/review");
        setMemberships(response.data);
      }
    } catch (error: any) {
      Alert.alert("Community administration unavailable", error?.response?.data?.detail ?? "Check your administrator scope.");
    } finally {
      setLoading(false);
    }
  }, [section]);

  useEffect(() => {
    const timer = setTimeout(() => { void load(); }, 0);
    return () => clearTimeout(timer);
  }, [load]);

  async function decide(request: MembershipRequest, status: "active" | "rejected") {
    if (status === "rejected" && note.trim().length < 3) {
      Alert.alert("Reason required", "Provide a reason before rejecting membership.");
      return;
    }
    try {
      await api.patch(`/api/community/memberships/${request.id}`, {
        status,
        review_note: note.trim() || undefined,
      });
      setNote("");
      await load();
    } catch (error: any) {
      Alert.alert("Review failed", error?.response?.data?.detail ?? "You may not manage this parish.");
    }
  }

  async function revoke(assignment: Assignment) {
    try {
      await api.delete(`/api/community/role-assignments/${assignment.assignment_id}`, {
        params: { reason: "Revoked through the administrator management screen." },
      });
      await load();
    } catch (error: any) {
      Alert.alert("Revoke failed", error?.response?.data?.detail ?? "You may not revoke this role.");
    }
  }

  async function reviewSuggestion(suggestion: Suggestion, status: "under_review" | "in_discussion" | "accepted" | "implemented" | "declined" | "archived") {
    try {
      await api.patch(`/api/community/suggestions/${suggestion.id}`, {
        status,
        review_note: note.trim() || undefined,
      });
      setNote("");
      await load();
    } catch (error: any) {
      Alert.alert("Suggestion review failed", error?.response?.data?.detail ?? "You may not manage this scope.");
    }
  }

  if (loading) return <View style={styles.center}><ActivityIndicator color="#0B6623" /></View>;
  const showAssignments = section === "administrators";
  const showSuggestions = section === "suggestions";

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.title}>{showAssignments ? "Administrators" : showSuggestions ? "Suggestion Review" : "Parish Membership Review"}</Text>
      {!showAssignments && !showSuggestions && (
        <>
          <Text style={styles.help}>Only parish administrators and diocesan administrators within their scope can approve membership requests.</Text>
          <TextInput value={note} onChangeText={setNote} placeholder="Reason for a rejection (optional for approval)" style={styles.input} maxLength={1000} />
          {memberships.length === 0 ? <Text style={styles.help}>No membership requests are available in your scope.</Text> : memberships.map((item) => (
            <View key={item.id} style={styles.card}>
              <Text style={styles.name}>{item.full_name}</Text>
              <Text style={styles.help}>{item.email}</Text>
              <Text style={styles.help}>{item.parish_name} · {item.status}</Text>
              <View style={styles.actions}>
                <Pressable style={styles.button} onPress={() => decide(item, "active")}><Text style={styles.buttonText}>Approve</Text></Pressable>
                <Pressable style={[styles.button, styles.reject]} onPress={() => decide(item, "rejected")}><Text style={styles.buttonText}>Reject</Text></Pressable>
              </View>
            </View>
          ))}
        </>
      )}
      {showAssignments && (
        assignments.length === 0 ? <Text style={styles.help}>No scoped administrator assignments are available, or platform-admin access is required.</Text> : assignments.map((item) => (
          <View key={item.assignment_id} style={styles.card}>
            <Text style={styles.name}>{item.full_name}</Text>
            <Text style={styles.help}>{item.email}</Text>
            <Text style={styles.help}>{item.role} · {item.scope_type} #{item.scope_id ?? "global"}</Text>
            <Pressable style={[styles.button, styles.reject]} onPress={() => revoke(item)}>
              <Text style={styles.buttonText}>Revoke assignment</Text>
            </Pressable>
          </View>
        ))
      )}
      {showSuggestions && (
        <>
          <TextInput value={note} onChangeText={setNote} placeholder="Optional review note" style={styles.input} maxLength={1000} />
          {suggestions.length === 0 ? <Text style={styles.help}>No suggestions are available in your scope.</Text> : suggestions.map((item) => (
            <View key={item.id} style={styles.card}>
              <Text style={styles.name}>{item.category} · {item.scope_type} #{item.scope_id}{item.is_anonymous ? " · Anonymous" : ""}</Text>
              <Text style={styles.help}>{item.body}</Text>
              <Text style={styles.help}>Status: {item.status}</Text>
              <View style={styles.actions}>
                <Pressable style={styles.button} onPress={() => reviewSuggestion(item, "under_review")}><Text style={styles.buttonText}>Review</Text></Pressable>
                <Pressable style={styles.button} onPress={() => reviewSuggestion(item, "accepted")}><Text style={styles.buttonText}>Accept</Text></Pressable>
                <Pressable style={[styles.button, styles.reject]} onPress={() => reviewSuggestion(item, "declined")}><Text style={styles.buttonText}>Decline</Text></Pressable>
              </View>
            </View>
          ))}
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#F7F9F7" },
  content: { padding: 20, paddingBottom: 40 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  title: { fontSize: 25, color: "#0B6623", fontWeight: "800", marginBottom: 10 },
  help: { color: "#5E6A61", lineHeight: 20, marginVertical: 5 },
  input: { backgroundColor: "#fff", borderWidth: 1, borderColor: "#D5DED7", borderRadius: 9, padding: 12, marginVertical: 10 },
  card: { backgroundColor: "#fff", borderRadius: 12, padding: 14, marginVertical: 6, borderColor: "#E4EAE5", borderWidth: 1 },
  name: { color: "#193D25", fontWeight: "700", fontSize: 16 },
  actions: { flexDirection: "row", gap: 8 },
  button: { backgroundColor: "#0B6623", padding: 10, borderRadius: 8, marginTop: 9 },
  reject: { backgroundColor: "#A52A2A" },
  buttonText: { color: "#fff", fontWeight: "700" },
});
