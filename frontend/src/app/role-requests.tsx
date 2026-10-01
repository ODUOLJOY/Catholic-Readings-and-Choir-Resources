import { useCallback, useEffect, useMemo, useState } from "react";
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

type ScopeType = "parish" | "diocese" | "group";
type RoleOption = {
  role: string;
  label: string;
  scope: ScopeType;
};

type RoleRequest = {
  id: number;
  requested_role: string;
  scope_type: ScopeType;
  scope_id: number;
  status: string;
  reason: string;
  review_note?: string | null;
};

type CommunityGroup = { id: number; name: string };
type CommunityProfile = {
  parish_id: number | null;
  diocese_id: number | null;
  parish_membership_status?: string | null;
};

const roles: RoleOption[] = [
  { role: "parish_admin", label: "Parish Admin", scope: "parish" },
  { role: "diocesan_admin", label: "Diocesan Admin", scope: "diocese" },
  { role: "parish_music_director", label: "Parish Music Director", scope: "parish" },
  { role: "choir_director", label: "Choir Director", scope: "parish" },
  { role: "catechist", label: "Catechist", scope: "parish" },
  { role: "youth_coordinator", label: "Youth Coordinator", scope: "parish" },
  { role: "moderator", label: "Moderator", scope: "parish" },
  { role: "ministry_leader", label: "Ministry Leader", scope: "group" },
];

export default function RoleRequestsScreen() {
  const { mode } = useLocalSearchParams<{ mode?: string }>();
  const reviewing = mode === "review";
  const [profile, setProfile] = useState<CommunityProfile | null>(null);
  const [groups, setGroups] = useState<CommunityGroup[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [requests, setRequests] = useState<RoleRequest[]>([]);
  const [selectedRole, setSelectedRole] = useState<RoleOption>(roles[0]);
  const [reason, setReason] = useState("");
  const [ministry, setMinistry] = useState("");
  const [reviewNote, setReviewNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const requestedScopeId = useMemo(() => {
    if (!profile) return null;
    if (selectedRole.scope === "diocese") return profile.diocese_id;
    if (selectedRole.scope === "parish") return profile.parish_id;
    return selectedGroupId;
  }, [profile, selectedGroupId, selectedRole]);

  const load = useCallback(async () => {
    try {
      if (reviewing) {
        const response = await api.get<RoleRequest[]>("/api/community/role-requests/review");
        setRequests(response.data);
      } else {
        const [profileResponse, requestsResponse, groupsResponse] = await Promise.all([
          api.get<CommunityProfile>("/api/community/me"),
          api.get<RoleRequest[]>("/api/community/role-requests/mine"),
          api.get<CommunityGroup[]>("/api/community/groups/mine"),
        ]);
        setProfile(profileResponse.data);
        setRequests(requestsResponse.data);
        setGroups(groupsResponse.data);
      }
    } catch (error) {
      Alert.alert(
        "Unable to load requests",
        "Check your connection and your community permissions, then try again.",
      );
    } finally {
      setLoading(false);
    }
  }, [reviewing]);

  useEffect(() => {
    const timer = setTimeout(() => { void load(); }, 0);
    return () => clearTimeout(timer);
  }, [load]);

  async function submit() {
    if (!profile || !requestedScopeId) {
      Alert.alert(
        "Parish membership required",
        "Choose your parish in Profile and wait for a parish administrator to verify your membership before requesting a scoped role.",
      );
      return;
    }
    if (reason.trim().length < 10) {
      Alert.alert("More information required", "Please provide at least 10 characters explaining your request.");
      return;
    }
    setSaving(true);
    try {
      const response = await api.post("/api/community/role-requests", {
        requested_role: selectedRole.role,
        scope_type: selectedRole.scope,
        scope_id: requestedScopeId,
        ministry: ministry.trim() || undefined,
        reason: reason.trim(),
      });
      setRequests((current) => [response.data, ...current]);
      setReason("");
      setMinistry("");
      Alert.alert("Request submitted", "Your request is awaiting review by an authorized administrator.");
    } catch (error: any) {
      Alert.alert("Request not submitted", error?.response?.data?.detail ?? "Please try again.");
    } finally {
      setSaving(false);
    }
  }

  async function review(request: RoleRequest, status: "under_review" | "more_information_required" | "approved" | "rejected") {
    if ((status === "rejected" || status === "more_information_required") && reviewNote.trim().length === 0) {
      Alert.alert("Review note required", "Enter a reason for this decision.");
      return;
    }
    setSaving(true);
    try {
      await api.patch(`/api/community/role-requests/${request.id}`, { status, review_note: reviewNote.trim() || undefined });
      setReviewNote("");
      await load();
    } catch (error: any) {
      Alert.alert("Review failed", error?.response?.data?.detail ?? "Please try again.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <View style={styles.center}><ActivityIndicator color="#0B6623" /></View>;
  }

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.title}>{reviewing ? "Role Requests to Review" : "Request a Role"}</Text>
      {!reviewing && (
        <>
          <Text style={styles.help}>
            Requests are scoped to your verified parish, diocese, or an existing group. Approval creates an audited role assignment; it does not grant platform-wide access.
          </Text>
          <Text style={styles.sectionTitle}>Choose role</Text>
          <View style={styles.roles}>
            {roles.map((option) => (
              <Pressable
                key={option.role}
                style={[styles.roleChip, selectedRole.role === option.role && styles.roleSelected]}
                onPress={() => setSelectedRole(option)}
              >
                <Text style={[styles.roleText, selectedRole.role === option.role && styles.roleTextSelected]}>
                  {option.label}
                </Text>
              </Pressable>
            ))}
          </View>
          <Text style={styles.help}>
            Scope: {selectedRole.scope}{requestedScopeId ? ` #${requestedScopeId}` : " not selected"} · parish membership: {profile?.parish_membership_status ?? "not requested"}
          </Text>
          {selectedRole.scope === "group" && (
            <View style={styles.roles}>
              {groups.map((group) => (
                <Pressable
                  key={group.id}
                  style={[styles.roleChip, selectedGroupId === group.id && styles.roleSelected]}
                  onPress={() => setSelectedGroupId(group.id)}
                >
                  <Text style={[styles.roleText, selectedGroupId === group.id && styles.roleTextSelected]}>
                    {group.name}
                  </Text>
                </Pressable>
              ))}
              {groups.length === 0 && <Text style={styles.help}>Join a verified parish or diocesan group before requesting a group-scoped role.</Text>}
            </View>
          )}
          <Text style={styles.label}>Ministry/group name (if relevant)</Text>
          <TextInput value={ministry} onChangeText={setMinistry} style={styles.input} maxLength={100} />
          <Text style={styles.label}>Reason and relevant experience</Text>
          <TextInput
            value={reason}
            onChangeText={setReason}
            style={[styles.input, styles.multiline]}
            multiline
            maxLength={4000}
          />
          <Pressable style={styles.button} onPress={submit} disabled={saving}>
            <Text style={styles.buttonText}>{saving ? "Submitting..." : "Submit Request"}</Text>
          </Pressable>
        </>
      )}
      <Text style={styles.sectionTitle}>{reviewing ? "Pending requests" : "Your requests"}</Text>
      {requests.length === 0 ? (
        <Text style={styles.empty}>No role requests to display.</Text>
      ) : requests.map((request) => (
        <View key={request.id} style={styles.card}>
          <Text style={styles.cardTitle}>{request.requested_role.replaceAll("_", " ")}</Text>
          <Text style={styles.cardMeta}>{request.scope_type} #{request.scope_id} · {request.status}</Text>
          <Text style={styles.body}>{request.reason}</Text>
          {request.review_note ? <Text style={styles.note}>Review: {request.review_note}</Text> : null}
          {reviewing && request.status !== "approved" && request.status !== "rejected" && (
            <>
              <TextInput
                value={reviewNote}
                onChangeText={setReviewNote}
                placeholder="Review note (required for more information or rejection)"
                style={styles.input}
                maxLength={4000}
              />
              <View style={styles.actions}>
                <Pressable style={styles.smallButton} onPress={() => review(request, "under_review")} disabled={saving}>
                  <Text style={styles.buttonText}>Mark reviewing</Text>
                </Pressable>
                <Pressable style={styles.smallButton} onPress={() => review(request, "more_information_required")} disabled={saving || reviewNote.trim().length === 0}>
                  <Text style={styles.buttonText}>More info</Text>
                </Pressable>
                <Pressable style={styles.smallButton} onPress={() => review(request, "approved")} disabled={saving}>
                  <Text style={styles.buttonText}>Approve</Text>
                </Pressable>
                <Pressable style={[styles.smallButton, styles.rejectButton]} onPress={() => review(request, "rejected")} disabled={saving || reviewNote.trim().length === 0}>
                  <Text style={styles.buttonText}>Reject</Text>
                </Pressable>
              </View>
            </>
          )}
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#F7F9F7" },
  content: { padding: 20, paddingBottom: 40 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  title: { fontSize: 26, fontWeight: "800", color: "#0B6623", marginBottom: 12 },
  sectionTitle: { fontSize: 18, fontWeight: "700", color: "#183D24", marginTop: 22, marginBottom: 10 },
  help: { color: "#59665C", lineHeight: 21, marginBottom: 10 },
  roles: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  roleChip: { borderWidth: 1, borderColor: "#B9C9BD", borderRadius: 18, paddingHorizontal: 12, paddingVertical: 9 },
  roleSelected: { backgroundColor: "#0B6623", borderColor: "#0B6623" },
  roleText: { color: "#28412F", fontWeight: "600" },
  roleTextSelected: { color: "#fff" },
  label: { marginTop: 12, marginBottom: 6, fontWeight: "600", color: "#26382B" },
  input: { backgroundColor: "#fff", borderWidth: 1, borderColor: "#D5DED7", borderRadius: 10, padding: 12 },
  multiline: { minHeight: 110, textAlignVertical: "top" },
  button: { backgroundColor: "#0B6623", padding: 14, borderRadius: 10, alignItems: "center", marginTop: 14 },
  smallButton: { backgroundColor: "#0B6623", padding: 10, borderRadius: 8 },
  rejectButton: { backgroundColor: "#A52A2A" },
  buttonText: { color: "#fff", fontWeight: "700" },
  empty: { color: "#657168", paddingVertical: 14 },
  card: { backgroundColor: "#fff", padding: 15, borderRadius: 12, marginBottom: 10, borderWidth: 1, borderColor: "#E4EAE5" },
  cardTitle: { color: "#1D3C25", fontWeight: "700", fontSize: 16, textTransform: "capitalize" },
  cardMeta: { color: "#66736A", marginTop: 5, textTransform: "capitalize" },
  body: { color: "#333", marginTop: 8, lineHeight: 20 },
  note: { color: "#785500", marginTop: 8 },
  actions: { flexDirection: "row", gap: 8, marginTop: 12 },
});
