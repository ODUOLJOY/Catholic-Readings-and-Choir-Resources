import React, { useCallback, useEffect, useState } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";
import { router, useLocalSearchParams } from "expo-router";

import { EmptyState, ErrorState, LoadingState } from "@/components/ScreenStates";
import {
  communityService,
  describeError,
  MembershipRequest,
  RoleAssignmentView,
  RoleRequestView,
  SUGGESTION_STATUS_LABELS,
  SUGGESTION_STATUSES_REQUIRING_NOTE,
  SUGGESTION_TRANSITIONS,
  SuggestionDetail,
  SuggestionStatus,
  SuggestionSummary,
} from "@/services/communityService";

type Section = "memberships" | "suggestions" | "roles" | "administrators";

const SECTIONS: { key: Section; label: string }[] = [
  { key: "memberships", label: "Membership" },
  { key: "suggestions", label: "Suggestions" },
  { key: "roles", label: "Role requests" },
  { key: "administrators", label: "Administrators" },
];

const STATUS_BUTTONS: { key: SuggestionStatus; label: string }[] = [
  { key: "under_review", label: "Review" },
  { key: "needs_information", label: "Ask" },
  { key: "in_discussion", label: "Discuss" },
  { key: "accepted", label: "Accept" },
  { key: "escalated", label: "Escalate" },
  { key: "implemented", label: "Implemented" },
  { key: "declined", label: "Decline" },
  { key: "archived", label: "Archive" },
];

export default function CommunityAdminScreen() {
  const { section } = useLocalSearchParams<{ section?: string }>();
  const initialSection = SECTIONS.some((item) => item.key === section)
    ? (section as Section)
    : "memberships";
  const [active, setActive] = useState<Section>(initialSection);

  const [memberships, setMemberships] = useState<MembershipRequest[]>([]);
  const [suggestions, setSuggestions] = useState<SuggestionSummary[]>([]);
  const [roleRequests, setRoleRequests] = useState<RoleRequestView[]>([]);
  const [assignments, setAssignments] = useState<RoleAssignmentView[]>([]);

  const [note, setNote] = useState("");
  const [detail, setDetail] = useState<SuggestionDetail | null>(null);
  const [replyBody, setReplyBody] = useState("");
  const [internal, setInternal] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      if (active === "administrators") {
        setAssignments(await communityService.getAdministrators());
      } else if (active === "suggestions") {
        setSuggestions(await communityService.getReviewQueue());
      } else if (active === "roles") {
        setRoleRequests(await communityService.getReviewableRoleRequests());
      } else {
        setMemberships(await communityService.getReviewableMemberships());
      }
    } catch (loadError) {
      setError(
        describeError(
          loadError,
          "This administration queue is unavailable for your scope.",
        ),
      );
    } finally {
      setLoading(false);
    }
  }, [active]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setLoading(true);
      void load();
    }, 0);
    return () => clearTimeout(timer);
  }, [load]);

  async function decideMembership(
    request: MembershipRequest,
    status: "active" | "rejected",
  ) {
    if (status === "rejected" && note.trim().length < 3) {
      setError("A reason is required before rejecting a membership request.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await communityService.reviewMembership(request.id, status, note);
      setNote("");
      setNotice(`Membership for ${request.full_name} was ${status}.`);
      await load();
    } catch (decideError) {
      setError(describeError(decideError, "The membership decision was not saved."));
    } finally {
      setBusy(false);
    }
  }

  async function decideRoleRequest(
    request: RoleRequestView,
    status: "under_review" | "more_information_required" | "approved" | "rejected",
  ) {
    if (
      (status === "rejected" || status === "more_information_required") &&
      note.trim().length === 0
    ) {
      setError("A decision note is required to reject or ask for more information.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await communityService.decideRoleRequest(request.id, status, note);
      setNote("");
      setNotice("Role request decision recorded.");
      await load();
    } catch (decideError) {
      setError(describeError(decideError, "The role request decision was not saved."));
    } finally {
      setBusy(false);
    }
  }

  async function openSuggestion(suggestion: SuggestionSummary) {
    setError(null);
    try {
      setDetail(await communityService.getSuggestionDetail(suggestion.id));
    } catch (openError) {
      setError(describeError(openError, "That suggestion could not be opened."));
    }
  }

  async function updateStatus(
    suggestion: SuggestionSummary,
    status: SuggestionStatus,
  ) {
    if (SUGGESTION_STATUSES_REQUIRING_NOTE.includes(status) && note.trim().length === 0) {
      setError(
        `${SUGGESTION_STATUS_LABELS[status]} requires a note so the member knows what to do.`,
      );
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await communityService.updateSuggestion(suggestion.id, status, note);
      setNote("");
      setNotice(`Suggestion moved to ${SUGGESTION_STATUS_LABELS[status]}.`);
      if (detail?.id === suggestion.id) {
        setDetail(await communityService.getSuggestionDetail(suggestion.id));
      }
      await load();
    } catch (updateError) {
      setError(describeError(updateError, "The suggestion status was not changed."));
    } finally {
      setBusy(false);
    }
  }

  async function sendReply() {
    if (!detail) return;
    if (replyBody.trim().length === 0) {
      setError("Write a reply before sending it.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await communityService.replyToSuggestion(detail.id, replyBody.trim(), internal);
      setReplyBody("");
      setDetail(await communityService.getSuggestionDetail(detail.id));
      setNotice(internal ? "Internal note added." : "Reply sent to the member.");
    } catch (replyError) {
      setError(describeError(replyError, "The reply was not saved."));
    } finally {
      setBusy(false);
    }
  }

  async function revoke(assignment: RoleAssignmentView) {
    setBusy(true);
    setError(null);
    try {
      await communityService.revokeRoleAssignment(
        assignment.assignment_id,
        "Revoked from community administration.",
      );
      setNotice("Role assignment revoked and recorded in the audit log.");
      await load();
    } catch (revokeError) {
      setError(describeError(revokeError, "That role assignment could not be revoked."));
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <LoadingState label="Loading your administration queue…" />;
  }

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Community administration</Text>
      <Text style={styles.help}>
        Every queue below is filtered on the server by the scopes you are authorized for, so a
        parish administrator only ever sees their own parish.
      </Text>

      <View style={styles.tabs}>
        {SECTIONS.map((option) => (
          <Pressable
            key={option.key}
            style={[styles.tab, active === option.key && styles.tabActive]}
            onPress={() => {
              setActive(option.key);
              setDetail(null);
            }}
          >
            <Text style={[styles.tabText, active === option.key && styles.tabTextActive]}>
              {option.label}
            </Text>
          </Pressable>
        ))}
      </View>

      {error ? <ErrorState message={error} onRetry={() => setError(null)} retryLabel="Dismiss" /> : null}
      {notice ? <Text style={styles.notice}>{notice}</Text> : null}

      <TextInput
        value={note}
        onChangeText={setNote}
        placeholder="Decision or review note (required for rejections and requests for information)"
        style={styles.input}
        maxLength={4000}
      />

      {active === "memberships" ? (
        memberships.length === 0 ? (
          <EmptyState message="No membership requests are waiting in your scope." />
        ) : (
          memberships.map((item) => (
            <View key={item.id} style={styles.card}>
              <Text style={styles.name}>{item.full_name}</Text>
              <Text style={styles.help}>{item.email}</Text>
              <Text style={styles.help}>
                {item.parish_name} · {item.status}
              </Text>
              <View style={styles.actions}>
                <Pressable
                  style={styles.button}
                  onPress={() => void decideMembership(item, "active")}
                  disabled={busy}
                >
                  <Text style={styles.buttonText}>Approve</Text>
                </Pressable>
                <Pressable
                  style={[styles.button, styles.reject]}
                  onPress={() => void decideMembership(item, "rejected")}
                  disabled={busy}
                >
                  <Text style={styles.buttonText}>Reject</Text>
                </Pressable>
              </View>
            </View>
          ))
        )
      ) : null}

      {active === "suggestions" ? (
        suggestions.length === 0 ? (
          <EmptyState message="No suggestions are open in your scope." />
        ) : (
          suggestions.map((item) => {
            const allowed = SUGGESTION_TRANSITIONS[item.status] ?? [];
            return (
              <View key={item.id} style={styles.card}>
                <Text style={styles.name}>
                  {item.category} · {item.scope_type} #{item.scope_id}
                </Text>
                <Text style={styles.help}>{item.body}</Text>
                <Text style={styles.help}>
                  {SUGGESTION_STATUS_LABELS[item.status] ?? item.status}
                  {item.is_anonymous ? " · Anonymous" : ""}
                </Text>
                <View style={styles.actions}>
                  <Pressable
                    style={styles.link}
                    onPress={() => void openSuggestion(item)}
                  >
                    <Text style={styles.linkText}>Replies</Text>
                  </Pressable>
                  {allowed.map((next) => {
                    const button = STATUS_BUTTONS.find((entry) => entry.key === next);
                    if (!button) return null;
                    return (
                      <Pressable
                        key={next}
                        style={[styles.button, styles.small]}
                        onPress={() => void updateStatus(item, next)}
                        disabled={busy}
                      >
                        <Text style={styles.buttonText}>{button.label}</Text>
                      </Pressable>
                    );
                  })}
                </View>
              </View>
            );
          })
        )
      ) : null}

      {detail ? (
        <View style={styles.card}>
          <Text style={styles.name}>Suggestion #{detail.id}</Text>
          <Text style={styles.help}>{detail.body}</Text>
          <Text style={styles.help}>
            {SUGGESTION_STATUS_LABELS[detail.status] ?? detail.status}
            {detail.review_note ? ` · ${detail.review_note}` : ""}
          </Text>
          {detail.replies.length === 0 ? (
            <Text style={styles.help}>No replies yet.</Text>
          ) : (
            detail.replies.map((reply) => (
              <View key={reply.id} style={styles.reply}>
                <Text style={styles.help}>{reply.body}</Text>
                <Text style={styles.meta}>
                  {new Date(reply.created_at).toLocaleString()}
                  {reply.is_internal ? " · internal" : " · visible to the member"}
                </Text>
              </View>
            ))
          )}
          <TextInput
            value={replyBody}
            onChangeText={setReplyBody}
            placeholder="Reply to the member, or add an internal note"
            style={styles.input}
            maxLength={10000}
            multiline
          />
          <View style={styles.switchRow}>
            <Text style={styles.help}>Internal note (hidden from the member)</Text>
            <Switch value={internal} onValueChange={setInternal} trackColor={{ true: "#0B6623" }} />
          </View>
          <Pressable style={styles.button} onPress={sendReply} disabled={busy}>
            <Text style={styles.buttonText}>{busy ? "Sending…" : "Send reply"}</Text>
          </Pressable>
          <Pressable style={styles.link} onPress={() => setDetail(null)}>
            <Text style={styles.linkText}>Close thread</Text>
          </Pressable>
        </View>
      ) : null}

      {active === "roles" ? (
        roleRequests.length === 0 ? (
          <EmptyState message="No role requests are waiting in your scope." />
        ) : (
          roleRequests.map((item) => (
            <View key={item.id} style={styles.card}>
              <Text style={styles.name}>{item.requested_role.replaceAll("_", " ")}</Text>
              <Text style={styles.help}>
                {item.scope_type} #{item.scope_id} · {item.status}
              </Text>
              <Text style={styles.help}>{item.reason}</Text>
              {item.review_note ? <Text style={styles.meta}>Note: {item.review_note}</Text> : null}
              <View style={styles.actions}>
                <Pressable
                  style={[styles.button, styles.small]}
                  onPress={() => void decideRoleRequest(item, "under_review")}
                  disabled={busy}
                >
                  <Text style={styles.buttonText}>Reviewing</Text>
                </Pressable>
                <Pressable
                  style={[styles.button, styles.small]}
                  onPress={() => void decideRoleRequest(item, "more_information_required")}
                  disabled={busy}
                >
                  <Text style={styles.buttonText}>More info</Text>
                </Pressable>
                <Pressable
                  style={[styles.button, styles.small]}
                  onPress={() => void decideRoleRequest(item, "approved")}
                  disabled={busy}
                >
                  <Text style={styles.buttonText}>Approve</Text>
                </Pressable>
                <Pressable
                  style={[styles.button, styles.small, styles.reject]}
                  onPress={() => void decideRoleRequest(item, "rejected")}
                  disabled={busy}
                >
                  <Text style={styles.buttonText}>Reject</Text>
                </Pressable>
              </View>
            </View>
          ))
        )
      ) : null}

      {active === "administrators" ? (
        assignments.length === 0 ? (
          <EmptyState message="No scoped administrator assignments are available to you." />
        ) : (
          assignments.map((item) => (
            <View key={item.assignment_id} style={styles.card}>
              <Text style={styles.name}>{item.full_name}</Text>
              <Text style={styles.help}>{item.email}</Text>
              <Text style={styles.help}>
                {item.role} · {item.scope_type} #{item.scope_id ?? "global"}
              </Text>
              <Pressable
                style={[styles.button, styles.reject]}
                onPress={() => void revoke(item)}
                disabled={busy}
              >
                <Text style={styles.buttonText}>Revoke assignment</Text>
              </Pressable>
            </View>
          ))
        )
      ) : null}

      <Pressable style={styles.link} onPress={() => router.push("/community-audit")}>
        <Text style={styles.linkText}>Open administrative audit log</Text>
      </Pressable>
      <Pressable style={styles.link} onPress={() => router.push("/role-requests?mode=review")}>
        <Text style={styles.linkText}>Open full role request screen</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#F7F9F7" },
  content: { padding: 20, paddingBottom: 44 },
  title: { fontSize: 25, color: "#0B6623", fontWeight: "800", marginBottom: 8 },
  help: { color: "#5E6A61", lineHeight: 20 },
  meta: { color: "#7A847D", fontSize: 12, marginTop: 4 },
  tabs: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 14 },
  tab: {
    borderWidth: 1,
    borderColor: "#B9C9BD",
    borderRadius: 18,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  tabActive: { backgroundColor: "#0B6623", borderColor: "#0B6623" },
  tabText: { color: "#28412F", fontWeight: "600" },
  tabTextActive: { color: "#fff" },
  input: {
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: "#D5DED7",
    borderRadius: 9,
    padding: 12,
    marginVertical: 10,
    minHeight: 60,
    textAlignVertical: "top",
  },
  card: {
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 14,
    marginVertical: 6,
    borderColor: "#E4EAE5",
    borderWidth: 1,
    gap: 4,
  },
  reply: { backgroundColor: "#F2F6F3", borderRadius: 8, padding: 10, marginTop: 6 },
  name: { color: "#193D25", fontWeight: "700", fontSize: 16 },
  actions: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 9 },
  button: {
    backgroundColor: "#0B6623",
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 8,
  },
  small: { paddingVertical: 8, paddingHorizontal: 10 },
  reject: { backgroundColor: "#A52A2A" },
  buttonText: { color: "#fff", fontWeight: "700" },
  link: { paddingVertical: 8 },
  linkText: { color: "#0B6623", fontWeight: "700", fontSize: 13 },
  switchRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 6,
  },
  notice: {
    color: "#1B4A2A",
    backgroundColor: "#EDF3EE",
    padding: 12,
    borderRadius: 10,
    marginTop: 12,
    lineHeight: 20,
  },
});