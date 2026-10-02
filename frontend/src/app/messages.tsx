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
import {
  CommunityMember,
  CommunityMessage,
  ConversationSummary,
  communityService,
} from "@/services/communityService";

export default function MessagesScreen() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [members, setMembers] = useState<CommunityMember[]>([]);
  const [memberQuery, setMemberQuery] = useState("");
  const [activeId, setActiveId] = useState<number | null>(null);
  const [messages, setMessages] = useState<CommunityMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [conversationList, memberList] = await Promise.all([
        communityService.getConversations(),
        communityService.searchMembers(),
      ]);
      setConversations(conversationList);
      setMembers(memberList);
    } catch (cause: any) {
      setError(
        cause?.response?.data?.detail ??
          "Could not load messages. Check your connection and try again.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => { void load(); }, 0);
    return () => clearTimeout(timer);
  }, [load]);

  async function openConversation(conversation: ConversationSummary) {
    setActiveId(conversation.id);
    try {
      const history = await communityService.getMessages(conversation.id);
      setMessages([...history].reverse());
      await communityService.markRead(conversation.id);
      setConversations((current) =>
        current.map((item) =>
          item.id === conversation.id ? { ...item, unread_count: 0 } : item,
        ),
      );
    } catch (error: any) {
      Alert.alert("Conversation unavailable", error?.response?.data?.detail ?? "Try again.");
    }
  }

  async function startDirect(member: CommunityMember) {
    if (busy) return;
    setBusy(true);
    try {
      const conversation = await communityService.startDirectConversation(member.id);
      const refreshed = await communityService.getConversations();
      setConversations(refreshed);
      await openConversation(conversation);
    } catch (error: any) {
      Alert.alert("Could not start conversation", error?.response?.data?.detail ?? "Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function searchMembers() {
    try {
      const results = await communityService.searchMembers(memberQuery.trim() || undefined);
      setMembers(results);
    } catch {
      // Keep the current list on transient search failures.
    }
  }

  async function send() {
    if (activeId === null || !draft.trim() || busy) return;
    setBusy(true);
    try {
      const created = await communityService.sendMessage(activeId, draft.trim());
      setMessages((current) => [...current, created]);
      setConversations((current) =>
        current.map((item) =>
          item.id === activeId
            ? {
                ...item,
                last_message: {
                  id: created.id,
                  sender_id: created.sender_id,
                  body: created.body,
                  created_at: created.created_at,
                },
              }
            : item,
        ),
      );
      setDraft("");
    } catch (error: any) {
      Alert.alert("Message not sent", error?.response?.data?.detail ?? "Try again.");
    } finally {
      setBusy(false);
    }
  }

  function conversationTitle(conversation: ConversationSummary) {
    if (conversation.conversation_type === "direct") {
      return conversation.participant?.full_name ?? "Direct message";
    }
    if (conversation.scope_type) {
      return `${conversation.scope_type} conversation #${conversation.scope_id}`;
    }
    return `Conversation #${conversation.id}`;
  }

  if (loading) {
    return <View style={styles.center}><ActivityIndicator color="#0B6623" /></View>;
  }

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Messages</Text>
      <Text style={styles.help}>
        Private one-to-one conversations with verified members of your parish, plus your parish conversation.
      </Text>

      {error ? (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>{error}</Text>
          <Pressable
            style={styles.searchButton}
            onPress={() => { setLoading(true); void load(); }}
          >
            <Text style={styles.buttonText}>Retry</Text>
          </Pressable>
        </View>
      ) : null}

      <Text style={styles.sectionTitle}>Start a direct message</Text>
      <View style={styles.searchRow}>
        <TextInput
          value={memberQuery}
          onChangeText={setMemberQuery}
          style={[styles.input, styles.searchInput]}
          placeholder="Search parish members by name"
          maxLength={100}
        />
        <Pressable style={styles.searchButton} onPress={searchMembers} disabled={busy}>
          <Text style={styles.buttonText}>Search</Text>
        </Pressable>
      </View>
      <View style={styles.members}>
        {members.map((member) => (
          <Pressable
            key={member.id}
            style={styles.memberChip}
            onPress={() => startDirect(member)}
            disabled={busy}
          >
            <Text style={styles.memberText}>{member.full_name}</Text>
          </Pressable>
        ))}
        {members.length === 0 && (
          <Text style={styles.empty}>No parish members available to message yet.</Text>
        )}
      </View>

      <Text style={styles.sectionTitle}>Conversations</Text>
      {conversations.length === 0 ? (
        <Text style={styles.empty}>No conversations yet.</Text>
      ) : conversations.map((conversation) => (
        <Pressable
          key={conversation.id}
          style={[styles.card, activeId === conversation.id && styles.cardActive]}
          onPress={() => openConversation(conversation)}
        >
          <View style={styles.cardHeader}>
            <Text style={styles.cardTitle}>{conversationTitle(conversation)}</Text>
            {conversation.unread_count > 0 && (
              <View style={styles.badge}>
                <Text style={styles.badgeText}>{conversation.unread_count}</Text>
              </View>
            )}
          </View>
          {conversation.last_message ? (
            <Text style={styles.preview} numberOfLines={1}>
              {conversation.last_message.body}
            </Text>
          ) : (
            <Text style={styles.preview}>No messages yet.</Text>
          )}
        </Pressable>
      ))}

      {activeId !== null && (
        <View style={styles.chat}>
          <Text style={styles.sectionTitle}>
            {conversationTitle(
              conversations.find((item) => item.id === activeId) ?? {
                id: activeId,
                conversation_type: "scope",
                scope_type: null,
                scope_id: null,
                group_id: null,
                created_by: 0,
                created_at: "",
                unread_count: 0,
                is_muted: false,
                last_message: null,
              },
            )}
          </Text>
          {messages.map((message) => (
            <View key={message.id} style={styles.message}>
              <Text style={styles.body}>{message.body}</Text>
              <Text style={styles.meta}>{new Date(message.created_at).toLocaleString()}</Text>
            </View>
          ))}
          <TextInput
            value={draft}
            onChangeText={setDraft}
            style={styles.input}
            placeholder="Write a message"
            maxLength={10000}
          />
          <Pressable style={styles.button} onPress={send} disabled={busy}>
            <Text style={styles.buttonText}>{busy ? "Sending..." : "Send message"}</Text>
          </Pressable>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#F7F9F7" },
  content: { padding: 18, paddingBottom: 40 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  title: { fontSize: 27, fontWeight: "800", color: "#0B6623" },
  help: { color: "#59665C", lineHeight: 21, marginTop: 6 },
  errorBanner: { backgroundColor: "#FDECEA", borderColor: "#F3C2BD", borderWidth: 1, borderRadius: 10, padding: 12, marginTop: 12, gap: 8 },
  errorText: { color: "#8A1C13", lineHeight: 20 },
  sectionTitle: { fontSize: 18, fontWeight: "700", color: "#183D24", marginTop: 20, marginBottom: 10 },
  searchRow: { flexDirection: "row", gap: 8, alignItems: "center" },
  searchInput: { flex: 1 },
  input: { backgroundColor: "#fff", borderWidth: 1, borderColor: "#D5DED7", borderRadius: 10, padding: 12 },
  searchButton: { backgroundColor: "#0B6623", paddingHorizontal: 16, paddingVertical: 13, borderRadius: 10 },
  members: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 10 },
  memberChip: { borderWidth: 1, borderColor: "#B8C8BB", borderRadius: 18, paddingHorizontal: 12, paddingVertical: 8 },
  memberText: { color: "#28412F", fontWeight: "600" },
  card: { backgroundColor: "#fff", padding: 14, borderRadius: 12, borderWidth: 1, borderColor: "#E4EAE5", marginBottom: 9 },
  cardActive: { borderColor: "#0B6623" },
  cardHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  cardTitle: { color: "#1D3C25", fontWeight: "700", fontSize: 16, flex: 1 },
  preview: { color: "#66736A", marginTop: 6 },
  badge: { backgroundColor: "#C62828", borderRadius: 10, minWidth: 20, paddingHorizontal: 6, paddingVertical: 2, alignItems: "center" },
  badgeText: { color: "#fff", fontWeight: "700", fontSize: 12 },
  chat: { marginTop: 16, padding: 12, backgroundColor: "#EDF3EE", borderRadius: 12 },
  message: { backgroundColor: "#fff", padding: 10, borderRadius: 10, marginBottom: 6 },
  body: { color: "#39463C", lineHeight: 20 },
  meta: { color: "#788279", marginTop: 4, fontSize: 12 },
  button: { backgroundColor: "#0B6623", padding: 12, alignItems: "center", borderRadius: 9, marginTop: 9 },
  buttonText: { color: "#fff", fontWeight: "700" },
  empty: { color: "#657168", paddingVertical: 10 },
});
