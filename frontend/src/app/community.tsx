import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";
import { router } from "expo-router";
import { api } from "@/lib/api";

type Announcement = { id: number; title: string; body: string; announcement_type: string };
type EventItem = { id: number; title: string; description?: string | null; starts_at: string; location?: string | null };
type Intention = { id: number; intention: string; visibility: string; is_mine: boolean };
type Conversation = { id: number; scope_type: string; scope_id: number };
type Message = { id: number; sender_id: number; body: string; created_at: string };
type CommunityProfile = { parish_id: number | null; diocese_id: number | null; parish_membership_status: string | null; roles: { role: string; scope_type: string; scope_id: number }[] };

const suggestionCategories = [
  ["liturgy", "Liturgy"],
  ["youth", "Youth"],
  ["choir_music", "Choir/Music"],
  ["catechesis", "Catechesis"],
  ["parish_activities", "Parish activities"],
  ["charity", "Charity"],
  ["evangelization", "Evangelization"],
  ["technology", "Technology"],
  ["community", "Community"],
  ["other", "Other"],
] as const;

export default function CommunityScreen() {
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [intentions, setIntentions] = useState<Intention[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [profile, setProfile] = useState<CommunityProfile | null>(null);
  const [suggestion, setSuggestion] = useState("");
  const [suggestionCategory, setSuggestionCategory] = useState<string>("community");
  const [anonymousSuggestion, setAnonymousSuggestion] = useState(true);
  const [prayer, setPrayer] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [conversationId, setConversationId] = useState<number | null>(null);

  const loadCommunity = useCallback(async () => {
    try {
      const [profileResponse, announcementResponse, eventResponse, intentionResponse, conversationResponse] = await Promise.all([
        api.get<CommunityProfile>("/api/community/me"),
        api.get<Announcement[]>("/api/community/announcements"),
        api.get<EventItem[]>("/api/community/events"),
        api.get<Intention[]>("/api/community/prayer-intentions"),
        api.get<Conversation[]>("/api/community/conversations"),
      ]);
      setProfile(profileResponse.data);
      setAnnouncements(announcementResponse.data);
      setEvents(eventResponse.data);
      setIntentions(intentionResponse.data);
      setConversations(conversationResponse.data);
    } catch (error) {
      Alert.alert("Community unavailable", "Could not load community information. Check connectivity and parish membership.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => { void loadCommunity(); }, 0);
    return () => clearTimeout(timer);
  }, [loadCommunity]);

  async function requestMembership() {
    setSaving(true);
    try {
      await api.post("/api/community/memberships/request");
      Alert.alert("Request sent", "A parish administrator will review your parish membership.");
      await loadCommunity();
    } catch (error: any) {
      Alert.alert("Membership request failed", error?.response?.data?.detail ?? "Please select a parish in Profile first.");
    } finally {
      setSaving(false);
    }
  }

  async function submitSuggestion() {
    if (!profile?.parish_id) {
      Alert.alert("Parish required", "Select a parish in Profile before submitting a parish suggestion.");
      return;
    }
    if (suggestion.trim().length < 10) {
      Alert.alert("Suggestion is too short", "Please provide at least 10 characters.");
      return;
    }
    setSaving(true);
    try {
      await api.post("/api/community/suggestions", {
        category: suggestionCategory,
        body: suggestion.trim(),
        scope_type: "parish",
        scope_id: profile.parish_id,
        is_anonymous: anonymousSuggestion,
      });
      setSuggestion("");
      Alert.alert("Suggestion submitted", "Your suggestion is visible only to authorized reviewers.");
    } catch (error: any) {
      Alert.alert("Suggestion not submitted", error?.response?.data?.detail ?? "Please try again.");
    } finally {
      setSaving(false);
    }
  }

  async function submitPrayer() {
    if (!prayer.trim()) return;
    setSaving(true);
    try {
      const response = await api.post("/api/community/prayer-intentions", {
        intention: prayer.trim(),
        visibility: "private",
      });
      setIntentions((current) => [
        { ...response.data, is_mine: true },
        ...current,
      ]);
      setPrayer("");
    } catch (error: any) {
      Alert.alert("Prayer intention not saved", error?.response?.data?.detail ?? "Please try again.");
    } finally {
      setSaving(false);
    }
  }

  async function openParishConversation() {
    if (!profile?.parish_id || profile.parish_membership_status !== "active") {
      Alert.alert("Verified membership required", "Parish conversations are available after a parish administrator verifies your membership.");
      return;
    }
    setSaving(true);
    try {
      const response = await api.post<Conversation>("/api/community/conversations", {
        scope_type: "parish",
        scope_id: profile.parish_id,
      });
      setConversationId(response.data.id);
      if (!conversations.some((item) => item.id === response.data.id)) {
        setConversations((current) => [response.data, ...current]);
      }
      const messagesResponse = await api.get<Message[]>(`/api/community/conversations/${response.data.id}/messages`);
      setMessages(messagesResponse.data.reverse());
    } catch (error: any) {
      Alert.alert("Conversation unavailable", error?.response?.data?.detail ?? "Please try again.");
    } finally {
      setSaving(false);
    }
  }

  async function sendMessage() {
    if (!conversationId || !message.trim()) return;
    setSaving(true);
    try {
      const response = await api.post<Message>(`/api/community/conversations/${conversationId}/messages`, {
        body: message.trim(),
      });
      setMessages((current) => [...current, response.data]);
      setMessage("");
    } catch (error: any) {
      Alert.alert("Message not sent", error?.response?.data?.detail ?? "Please try again.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <View style={styles.center}><ActivityIndicator color="#0B6623" size="large" /></View>;
  }

  const announcementScope = profile?.roles.find((assignment) =>
    assignment.role === "parish_admin" || assignment.role === "diocesan_admin",
  );

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Catholic Community</Text>
      <Text style={styles.subtitle}>
        Official announcements, parish events, suggestions, prayer intentions, and parish conversation.
      </Text>

      {profile?.parish_id && profile.parish_membership_status !== "active" && (
        <View style={styles.notice}>
          <Text style={styles.cardTitle}>Parish membership: {profile.parish_membership_status ?? "not requested"}</Text>
          <Text style={styles.body}>Parish communications are available after authorized membership verification.</Text>
          <Pressable style={styles.secondaryButton} onPress={requestMembership} disabled={saving}>
            <Text style={styles.secondaryText}>Request / retry membership review</Text>
          </Pressable>
        </View>
      )}

      <Section title="Official announcements">
        {announcements.length ? announcements.map((item) => (
          <View key={item.id} style={styles.card}>
            <Text style={styles.badge}>OFFICIAL · {item.announcement_type.toUpperCase()}</Text>
            <Text style={styles.cardTitle}>{item.title}</Text>
            <Text style={styles.body}>{item.body}</Text>
          </View>
        )) : <Text style={styles.empty}>No published announcements for your available scopes.</Text>}
      </Section>

      {announcementScope && (
        <AnnouncementComposer
          scopeType={announcementScope.scope_type === "diocese" ? "diocese" : "parish"}
          scopeId={announcementScope.scope_id}
        />
      )}
      {announcementScope && (
        <EventComposer
          scopeType={announcementScope.scope_type === "diocese" ? "diocese" : "parish"}
          scopeId={announcementScope.scope_id}
          onPublished={loadCommunity}
        />
      )}

      <Section title="Upcoming parish and diocesan events">
        {events.length ? events.map((item) => (
          <View key={item.id} style={styles.card}>
            <Text style={styles.cardTitle}>{item.title}</Text>
            <Text style={styles.body}>{new Date(item.starts_at).toLocaleString()}</Text>
            {item.location ? <Text style={styles.body}>{item.location}</Text> : null}
            {item.description ? <Text style={styles.body}>{item.description}</Text> : null}
          </View>
        )) : <Text style={styles.empty}>No published upcoming events.</Text>}
      </Section>

      <Section title="Private suggestion box">
        <Text style={styles.body}>Suggestions are private to authorized parish or diocesan reviewers.</Text>
        <View style={styles.categories}>
          {suggestionCategories.map(([key, label]) => (
            <Pressable
              key={key}
              style={[styles.categoryChip, suggestionCategory === key && styles.categorySelected]}
              onPress={() => setSuggestionCategory(key)}
            >
              <Text style={[styles.categoryLabel, suggestionCategory === key && styles.categoryLabelSelected]}>{label}</Text>
            </Pressable>
          ))}
        </View>
        <TextInput value={suggestion} onChangeText={setSuggestion} style={[styles.input, styles.multiline]} multiline maxLength={10000} placeholder="Share a constructive suggestion" />
        <View style={styles.privacyRow}>
          <Text style={styles.body}>Submit anonymously</Text>
          <Switch value={anonymousSuggestion} onValueChange={setAnonymousSuggestion} trackColor={{ true: "#0B6623" }} />
        </View>
        <Pressable style={styles.button} onPress={submitSuggestion} disabled={saving}>
          <Text style={styles.buttonText}>Submit anonymous suggestion</Text>
        </Pressable>
      </Section>

      <Section title="Prayer intentions">
        <TextInput value={prayer} onChangeText={setPrayer} style={[styles.input, styles.multiline]} multiline maxLength={2000} placeholder="Add a private prayer intention" />
        <Pressable style={styles.button} onPress={submitPrayer} disabled={saving}>
          <Text style={styles.buttonText}>Save private intention</Text>
        </Pressable>
        {intentions.map((item) => (
          <View key={item.id} style={styles.card}>
            <Text style={styles.body}>{item.intention}</Text>
            <Text style={styles.cardMeta}>{item.is_mine ? "Yours" : "Shared"} · {item.visibility}</Text>
          </View>
        ))}
      </Section>

      <Section title="Parish conversation">
        <Text style={styles.body}>Only verified members of your selected parish can access its conversation.</Text>
        <Pressable style={styles.button} onPress={openParishConversation} disabled={saving}>
          <Text style={styles.buttonText}>Open parish conversation</Text>
        </Pressable>
        {conversations.filter((item) => item.scope_type === "parish").map((item) => (
          <Pressable key={item.id} style={styles.secondaryButton} onPress={async () => {
            setConversationId(item.id);
            try {
              const response = await api.get<Message[]>(`/api/community/conversations/${item.id}/messages`);
              setMessages(response.data.reverse());
            } catch (error: any) {
              Alert.alert("Conversation unavailable", error?.response?.data?.detail ?? "Membership is required.");
            }
          }}>
            <Text style={styles.secondaryText}>Open conversation #{item.id}</Text>
          </Pressable>
        ))}
        {conversationId !== null && (
          <View style={styles.chat}>
            {messages.map((item) => (
              <View key={item.id} style={styles.message}>
                <Text style={styles.body}>{item.body}</Text>
                <Text style={styles.cardMeta}>{new Date(item.created_at).toLocaleString()}</Text>
              </View>
            ))}
            <TextInput value={message} onChangeText={setMessage} style={styles.input} maxLength={10000} placeholder="Write a message" />
            <Pressable style={styles.button} onPress={sendMessage} disabled={saving}>
              <Text style={styles.buttonText}>Send message</Text>
            </Pressable>
          </View>
        )}
      </Section>

      <Pressable style={styles.secondaryButton} onPress={() => router.push("/messages")}>
        <Text style={styles.secondaryText}>Private messages</Text>
      </Pressable>
      <Pressable style={styles.secondaryButton} onPress={() => router.push("/role-requests")}>
        <Text style={styles.secondaryText}>Request a community role</Text>
      </Pressable>
      <Pressable style={styles.secondaryButton} onPress={() => router.push("/notification-preferences")}>
        <Text style={styles.secondaryText}>Notification preferences</Text>
      </Pressable>
    </ScrollView>
  );
}

function AnnouncementComposer({ scopeType, scopeId }: { scopeType: "parish" | "diocese"; scopeId: number }) {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [saving, setSaving] = useState(false);
  async function publish() {
    if (!title.trim() || !body.trim()) return;
    setSaving(true);
    try {
      const created = await api.post("/api/community/announcements", {
        title: title.trim(),
        body: body.trim(),
        announcement_type: "parish",
        audience_type: scopeType,
        audience_id: scopeId,
        status: "draft",
      });
      await api.post(`/api/community/announcements/${created.data.id}/publish`);
      Alert.alert("Announcement published", `Your scoped ${scopeType} announcement is now published.`);
      setTitle("");
      setBody("");
    } catch (error: any) {
      Alert.alert("Announcement not published", error?.response?.data?.detail ?? "Check your parish administration scope.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Section title={`Publish ${scopeType} announcement`}>
      <TextInput value={title} onChangeText={setTitle} style={styles.input} placeholder="Announcement title" maxLength={200} />
      <TextInput value={body} onChangeText={setBody} style={[styles.input, styles.multiline]} placeholder="Official parish announcement" multiline maxLength={20000} />
      <Pressable style={styles.button} onPress={publish} disabled={saving}>
        <Text style={styles.buttonText}>{saving ? "Publishing..." : "Publish scoped announcement"}</Text>
      </Pressable>
    </Section>
  );
}

function EventComposer({
  scopeType,
  scopeId,
  onPublished,
}: {
  scopeType: "parish" | "diocese";
  scopeId: number;
  onPublished: () => Promise<void>;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [startsAt, setStartsAt] = useState("");
  const [location, setLocation] = useState("");
  const [saving, setSaving] = useState(false);

  async function publish() {
    if (!title.trim() || Number.isNaN(Date.parse(startsAt))) {
      Alert.alert("Event details required", "Enter a title and a valid date/time, such as 2026-12-24T18:00:00Z.");
      return;
    }
    setSaving(true);
    try {
      const created = await api.post("/api/community/events", {
        title: title.trim(),
        description: description.trim() || undefined,
        scope_type: scopeType,
        scope_id: scopeId,
        starts_at: new Date(startsAt).toISOString(),
        location: location.trim() || undefined,
      });
      await api.post(`/api/community/events/${created.data.id}/publish`);
      await onPublished();
      setTitle("");
      setDescription("");
      setLocation("");
      Alert.alert("Event published", `The event is now visible to verified ${scopeType} members.`);
    } catch (error: any) {
      Alert.alert("Event not published", error?.response?.data?.detail ?? "Check your scope and event details.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Section title={`Publish ${scopeType} event`}>
      <TextInput value={title} onChangeText={setTitle} style={styles.input} placeholder="Event title" maxLength={200} />
      <TextInput value={description} onChangeText={setDescription} style={[styles.input, styles.multiline]} placeholder="Description" multiline maxLength={10000} />
      <TextInput value={startsAt} onChangeText={setStartsAt} style={styles.input} placeholder="2026-12-24T18:00:00Z" />
      <TextInput value={location} onChangeText={setLocation} style={styles.input} placeholder="Location" maxLength={255} />
      <Pressable style={styles.button} onPress={publish} disabled={saving}>
        <Text style={styles.buttonText}>{saving ? "Publishing..." : "Publish scoped event"}</Text>
      </Pressable>
    </Section>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <View style={styles.section}><Text style={styles.sectionTitle}>{title}</Text>{children}</View>;
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#F7F9F7" },
  content: { padding: 18, paddingBottom: 40 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  title: { fontSize: 27, fontWeight: "800", color: "#0B6623" },
  subtitle: { color: "#59665C", lineHeight: 21, marginTop: 6 },
  section: { marginTop: 22 },
  sectionTitle: { fontSize: 19, fontWeight: "700", color: "#183D24", marginBottom: 10 },
  empty: { color: "#657168", paddingVertical: 10 },
  card: { backgroundColor: "#fff", padding: 14, borderRadius: 12, borderColor: "#E3EAE4", borderWidth: 1, marginBottom: 9 },
  notice: { backgroundColor: "#FFF8E1", padding: 14, borderRadius: 12, marginTop: 14 },
  badge: { color: "#0B6623", fontWeight: "800", fontSize: 11, marginBottom: 6 },
  cardTitle: { fontWeight: "700", fontSize: 16, color: "#1D3C25" },
  body: { color: "#39463C", lineHeight: 20, marginTop: 5 },
  cardMeta: { color: "#788279", marginTop: 5, fontSize: 12 },
  input: { backgroundColor: "#fff", borderWidth: 1, borderColor: "#D5DED7", borderRadius: 10, padding: 12, marginTop: 7 },
  multiline: { minHeight: 82, textAlignVertical: "top" },
  button: { backgroundColor: "#0B6623", padding: 12, alignItems: "center", borderRadius: 9, marginTop: 9 },
  buttonText: { color: "#fff", fontWeight: "700" },
  secondaryButton: { backgroundColor: "#EAF2EC", padding: 12, borderRadius: 9, marginTop: 9, alignItems: "center" },
  secondaryText: { color: "#0B6623", fontWeight: "700" },
  chat: { marginTop: 10, padding: 10, backgroundColor: "#EDF3EE", borderRadius: 10 },
  message: { alignSelf: "flex-start", backgroundColor: "#fff", padding: 9, borderRadius: 10, marginBottom: 6, maxWidth: "90%" },
  categories: { flexDirection: "row", flexWrap: "wrap", gap: 7, marginTop: 8 },
  categoryChip: { borderColor: "#B8C8BB", borderWidth: 1, borderRadius: 18, paddingHorizontal: 10, paddingVertical: 7 },
  categorySelected: { backgroundColor: "#0B6623", borderColor: "#0B6623" },
  categoryLabel: { color: "#35513C", fontSize: 12, fontWeight: "600" },
  categoryLabelSelected: { color: "#fff" },
  privacyRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: 8 },
});
