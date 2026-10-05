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
import { router } from "expo-router";

import { ReportModal } from "@/components/ReportModal";
import { EmptyState, ErrorState, LoadingState, SectionHeading } from "@/components/ScreenStates";
import {
  communityService,
  CommunityAnnouncement,
  CommunityEvent,
  CommunityHeader,
  defaultReportLabels,
  describeError,
  PrayerIntention,
  PrayerVisibility,
  ReportableResourceType,
  SUGGESTION_CATEGORIES,
  SUGGESTION_STATUS_LABELS,
  SuggestionDetail,
  SuggestionSummary,
} from "@/services/communityService";

const PRAYER_VISIBILITIES: { key: PrayerVisibility; label: string }[] = [
  { key: "private", label: "Only me" },
  { key: "parish", label: "My parish" },
  { key: "diocese", label: "My diocese" },
  { key: "public", label: "Anyone" },
];

type Reportable = { resourceType: ReportableResourceType; resourceId: number; label: string };

export default function CommunityScreen() {
  const [header, setHeader] = useState<CommunityHeader | null>(null);
  const [announcements, setAnnouncements] = useState<CommunityAnnouncement[]>([]);
  const [events, setEvents] = useState<CommunityEvent[]>([]);
  const [intentions, setIntentions] = useState<PrayerIntention[]>([]);
  const [mySuggestions, setMySuggestions] = useState<SuggestionSummary[]>([]);
  const [suggestionDetail, setSuggestionDetail] = useState<SuggestionDetail | null>(null);
  const [prayedFor, setPrayedFor] = useState<number[]>([]);

  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [reporting, setReporting] = useState<Reportable | null>(null);

  const [suggestion, setSuggestion] = useState("");
  const [suggestionCategory, setSuggestionCategory] = useState<string>("community");
  const [anonymousSuggestion, setAnonymousSuggestion] = useState(true);
  const [prayer, setPrayer] = useState("");
  const [prayerVisibility, setPrayerVisibility] = useState<PrayerVisibility>("private");

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const [
        headerResponse,
        announcementResponse,
        eventResponse,
        intentionResponse,
        suggestionResponse,
      ] = await Promise.all([
        communityService.getHeader(),
        communityService.getAnnouncements(),
        communityService.getEvents(),
        communityService.getPrayerIntentions(),
        communityService.getMySuggestions(),
      ]);
      setHeader(headerResponse);
      setAnnouncements(announcementResponse);
      setEvents(eventResponse);
      setIntentions(intentionResponse);
      setMySuggestions(suggestionResponse);
    } catch (error) {
      setLoadError(
        describeError(
          error,
          "The parish community could not be loaded. Check your connection and try again.",
        ),
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      void load();
    }, 0);
    return () => clearTimeout(timer);
  }, [load]);

  async function requestMembership() {
    setBusy(true);
    setFormError(null);
    try {
      await communityService.requestMembership();
      setNotice("Your request was sent. A parish administrator will review it.");
      await load();
    } catch (error) {
      setFormError(describeError(error, "The membership request could not be sent."));
    } finally {
      setBusy(false);
    }
  }

  async function submitSuggestion() {
    const parishId = header?.community?.parish_id;
    if (!parishId) {
      setFormError("Choose a parish in Profile before submitting a suggestion.");
      return;
    }
    if (suggestion.trim().length < 10) {
      setFormError("Please provide at least 10 characters so a reviewer understands it.");
      return;
    }
    setBusy(true);
    setFormError(null);
    try {
      await communityService.createSuggestion({
        category: suggestionCategory,
        body: suggestion.trim(),
        scope_type: "parish",
        scope_id: parishId,
        is_anonymous: anonymousSuggestion,
      });
      setSuggestion("");
      setNotice("Suggestion submitted. Only authorized reviewers can see it.");
      await load();
    } catch (error) {
      setFormError(describeError(error, "The suggestion was not submitted."));
    } finally {
      setBusy(false);
    }
  }

  async function openSuggestion(id: number) {
    setFormError(null);
    try {
      setSuggestionDetail(await communityService.getSuggestionDetail(id));
    } catch (error) {
      setFormError(describeError(error, "That suggestion could not be opened."));
    }
  }

  async function submitPrayer() {
    const body = prayer.trim();
    if (!body) return;
    setBusy(true);
    setFormError(null);
    try {
      const created = await communityService.createPrayerIntention(body, prayerVisibility);
      setIntentions((current) => [
        { ...created, is_mine: true },
        ...current,
      ]);
      setPrayer("");
      setNotice("Prayer intention saved.");
    } catch (error) {
      setFormError(describeError(error, "The intention was not saved."));
    } finally {
      setBusy(false);
    }
  }

  async function prayFor(intention: PrayerIntention) {
    setBusy(true);
    setFormError(null);
    try {
      const result = await communityService.prayForIntention(intention.id);
      setPrayedFor((current) =>
        result.status === "reacted" && !current.includes(intention.id)
          ? [...current, intention.id]
          : current,
      );
    } catch (error) {
      setFormError(describeError(error, "Your prayer could not be recorded."));
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <LoadingState label="Loading your parish community…" />;
  }

  const community = header?.community ?? null;

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Catholic Community</Text>
      <Text style={styles.subtitle}>
        Official announcements, parish events, suggestions, prayer intentions and parish
        conversation for your verified community.
      </Text>

      {loadError ? <ErrorState message={loadError} onRetry={() => void load()} /> : null}
      {notice ? <Text style={styles.notice}>{notice}</Text> : null}
      {formError ? <Text style={styles.formError}>{formError}</Text> : null}

      <SectionHeading>Your community</SectionHeading>
      {community ? (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>{community.parish_name}</Text>
          <Text style={styles.body}>
            {[
              community.diocese_name,
              community.deanery_name ? `${community.deanery_name} deanery` : null,
              `${community.member_count} verified members`,
            ]
              .filter(Boolean)
              .join(" · ")}
          </Text>
          {community.my_roles.length > 0 ? (
            <Text style={styles.cardMeta}>
              Roles: {community.my_roles.map((role) => role.role.replaceAll("_", " ")).join(", ")}
            </Text>
          ) : null}
          <Text style={styles.cardMeta}>{community.rules}</Text>
          <View style={styles.row}>
            <Pressable style={styles.secondaryButton} onPress={() => router.push("/messages")}>
              <Text style={styles.secondaryText}>Open conversations</Text>
            </Pressable>
            {community.can_manage || community.can_moderate ? (
              <Pressable
                style={styles.secondaryButton}
                onPress={() => router.push("/community-admin")}
              >
                <Text style={styles.secondaryText}>Administration</Text>
              </Pressable>
            ) : null}
          </View>
        </View>
      ) : (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>
            Parish membership: {header?.parish_membership_status ?? "not requested"}
          </Text>
          <Text style={styles.body}>
            {header?.unavailable_reason ??
              "Select a parish in Profile and request membership to join the parish community."}
          </Text>
          <Pressable style={styles.primaryButton} onPress={requestMembership} disabled={busy}>
            <Text style={styles.primaryText}>Request membership review</Text>
          </Pressable>
        </View>
      )}

      <SectionHeading>Official announcements</SectionHeading>
      {announcements.length === 0 ? (
        <EmptyState message="No published announcements are available for your scopes." />
      ) : (
        announcements.map((item) => (
          <View key={item.id} style={styles.card}>
            <Text style={styles.badge}>
              OFFICIAL · {item.announcement_type.toUpperCase()}
            </Text>
            <Text style={styles.cardTitle}>{item.title}</Text>
            <Text style={styles.body}>{item.body}</Text>
            <Pressable
              style={styles.linkButton}
              onPress={() =>
                setReporting({
                  resourceType: "announcement",
                  resourceId: item.id,
                  label: item.title,
                })
              }
            >
              <Text style={styles.linkText}>Report announcement</Text>
            </Pressable>
          </View>
        ))
      )}

      {community?.can_moderate ? (
        <AnnouncementComposer
          scopeType={community.diocese_id ? "diocese" : "parish"}
          scopeId={community.diocese_id ?? community.parish_id}
          onPublished={load}
        />
      ) : null}

      <SectionHeading>Upcoming events</SectionHeading>
      {events.length === 0 ? (
        <EmptyState message="No published upcoming events." />
      ) : (
        events.map((item) => (
          <View key={item.id} style={styles.card}>
            <Text style={styles.cardTitle}>{item.title}</Text>
            <Text style={styles.cardMeta}>{new Date(item.starts_at).toLocaleString()}</Text>
            {item.location ? <Text style={styles.body}>{item.location}</Text> : null}
            {item.description ? <Text style={styles.body}>{item.description}</Text> : null}
            <Pressable
              style={styles.linkButton}
              onPress={() =>
                setReporting({ resourceType: "event", resourceId: item.id, label: item.title })
              }
            >
              <Text style={styles.linkText}>Report event</Text>
            </Pressable>
          </View>
        ))
      )}

      {community?.can_moderate ? (
        <EventComposer
          scopeType={community.diocese_id ? "diocese" : "parish"}
          scopeId={community.diocese_id ?? community.parish_id}
          onPublished={load}
        />
      ) : null}

      <SectionHeading>Private suggestion box</SectionHeading>
      <Text style={styles.body}>
        Suggestions are visible only to authorized parish or diocesan reviewers. You can follow the
        status and read reviewer replies below.
      </Text>
      <View style={styles.chips}>
        {SUGGESTION_CATEGORIES.map((option) => (
          <Pressable
            key={option.key}
            style={[styles.chip, suggestionCategory === option.key && styles.chipSelected]}
            onPress={() => setSuggestionCategory(option.key)}
          >
            <Text
              style={[styles.chipText, suggestionCategory === option.key && styles.chipTextSelected]}
            >
              {option.label}
            </Text>
          </Pressable>
        ))}
      </View>
      <TextInput
        value={suggestion}
        onChangeText={setSuggestion}
        style={[styles.input, styles.multiline]}
        multiline
        maxLength={10000}
        placeholder="Share a constructive suggestion"
      />
      <View style={styles.switchRow}>
        <Text style={styles.body}>Submit anonymously to reviewers</Text>
        <Switch
          value={anonymousSuggestion}
          onValueChange={setAnonymousSuggestion}
          trackColor={{ true: "#0B6623" }}
        />
      </View>
      <Pressable style={styles.primaryButton} onPress={submitSuggestion} disabled={busy}>
        <Text style={styles.primaryText}>
          {anonymousSuggestion ? "Submit anonymous suggestion" : "Submit suggestion"}
        </Text>
      </Pressable>

      {mySuggestions.length > 0 ? (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Your suggestions</Text>
          {mySuggestions.map((item) => (
            <Pressable
              key={item.id}
              style={styles.rowBetween}
              onPress={() => void openSuggestion(item.id)}
            >
              <View style={styles.flex}>
                <Text style={styles.body} numberOfLines={2}>
                  {item.body}
                </Text>
                <Text style={styles.cardMeta}>
                  {SUGGESTION_STATUS_LABELS[item.status] ?? item.status}
                  {item.review_note ? ` · ${item.review_note}` : ""}
                </Text>
              </View>
              <Text style={styles.linkText}>Open</Text>
            </Pressable>
          ))}
        </View>
      ) : null}

      {suggestionDetail ? (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>
            {SUGGESTION_STATUS_LABELS[suggestionDetail.status] ?? suggestionDetail.status}
          </Text>
          <Text style={styles.body}>{suggestionDetail.body}</Text>
          {suggestionDetail.review_note ? (
            <Text style={styles.cardMeta}>Reviewer note: {suggestionDetail.review_note}</Text>
          ) : null}
          {suggestionDetail.replies.length === 0 ? (
            <Text style={styles.cardMeta}>No replies yet.</Text>
          ) : (
            suggestionDetail.replies.map((reply) => (
              <View key={reply.id} style={styles.reply}>
                <Text style={styles.body}>{reply.body}</Text>
                <Text style={styles.cardMeta}>
                  {new Date(reply.created_at).toLocaleString()}
                  {reply.is_internal ? " · internal note" : ""}
                </Text>
              </View>
            ))
          )}
          <Pressable style={styles.linkButton} onPress={() => setSuggestionDetail(null)}>
            <Text style={styles.linkText}>Close suggestion</Text>
          </Pressable>
        </View>
      ) : null}

      <SectionHeading>Prayer intentions</SectionHeading>
      <View style={styles.chips}>
        {PRAYER_VISIBILITIES.map((option) => (
          <Pressable
            key={option.key}
            style={[styles.chip, prayerVisibility === option.key && styles.chipSelected]}
            onPress={() => setPrayerVisibility(option.key)}
          >
            <Text
              style={[styles.chipText, prayerVisibility === option.key && styles.chipTextSelected]}
            >
              {option.label}
            </Text>
          </Pressable>
        ))}
      </View>
      <TextInput
        value={prayer}
        onChangeText={setPrayer}
        style={[styles.input, styles.multiline]}
        multiline
        maxLength={2000}
        placeholder="Add a prayer intention"
      />
      <Pressable style={styles.primaryButton} onPress={submitPrayer} disabled={busy}>
        <Text style={styles.primaryText}>Save intention</Text>
      </Pressable>
      {intentions.length === 0 ? (
        <EmptyState message="No prayer intentions are visible to you yet." />
      ) : (
        intentions.map((item) => (
          <View key={item.id} style={styles.card}>
            <Text style={styles.body}>{item.intention}</Text>
            <Text style={styles.cardMeta}>
              {item.is_mine ? "Yours" : "Shared"} · {item.visibility}
            </Text>
            <View style={styles.row}>
              <Pressable
                style={styles.secondaryButton}
                onPress={() => void prayFor(item)}
                disabled={busy || prayedFor.includes(item.id)}
              >
                <Text style={styles.secondaryText}>
                  {prayedFor.includes(item.id) ? "Praying" : "I am praying"}
                </Text>
              </Pressable>
              {!item.is_mine ? (
                <Pressable
                  style={styles.linkButton}
                  onPress={() =>
                    setReporting({
                      resourceType: "prayer_intention",
                      resourceId: item.id,
                      label: item.intention.slice(0, 40),
                    })
                  }
                >
                  <Text style={styles.linkText}>Report</Text>
                </Pressable>
              ) : null}
            </View>
          </View>
        ))
      )}

      <SectionHeading>Community settings</SectionHeading>
      <View style={styles.row}>
        <Pressable style={styles.secondaryButton} onPress={() => router.push("/messages")}>
          <Text style={styles.secondaryText}>Private messages</Text>
        </Pressable>
        <Pressable style={styles.secondaryButton} onPress={() => router.push("/role-requests")}>
          <Text style={styles.secondaryText}>Request a community role</Text>
        </Pressable>
      </View>
      <View style={styles.row}>
        <Pressable
          style={styles.secondaryButton}
          onPress={() => router.push("/notification-preferences")}
        >
          <Text style={styles.secondaryText}>Notification preferences</Text>
        </Pressable>
        <Pressable style={styles.secondaryButton} onPress={() => router.push("/community-audit")}>
          <Text style={styles.secondaryText}>Audit log</Text>
        </Pressable>
      </View>

      {reporting ? (
        <ReportModal
          visible
          onClose={() => setReporting(null)}
          resourceType={reporting.resourceType}
          resourceId={reporting.resourceId}
          onSubmit={communityService.submitReport}
          labels={defaultReportLabels}
          title={`Report ${reporting.label}`}
        />
      ) : null}
    </ScrollView>
  );
}

function AnnouncementComposer({
  scopeType,
  scopeId,
  onPublished,
}: {
  scopeType: "parish" | "diocese";
  scopeId: number;
  onPublished: () => Promise<void>;
}) {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function publish() {
    if (!title.trim() || !body.trim()) {
      setError("A title and message are both required.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const created = await communityService.createAnnouncement({
        title: title.trim(),
        body: body.trim(),
        audience_type: scopeType,
        audience_id: scopeId,
      });
      await communityService.publishAnnouncement(created.id);
      await onPublished();
      setTitle("");
      setBody("");
    } catch (publishError) {
      setError(
        describeError(publishError, "The announcement could not be published in your scope."),
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>Publish a {scopeType} announcement</Text>
      {error ? <Text style={styles.formError}>{error}</Text> : null}
      <TextInput
        value={title}
        onChangeText={setTitle}
        style={styles.input}
        placeholder="Announcement title"
        maxLength={200}
      />
      <TextInput
        value={body}
        onChangeText={setBody}
        style={[styles.input, styles.multiline]}
        placeholder="Official announcement"
        multiline
        maxLength={20000}
      />
      <Pressable style={styles.primaryButton} onPress={publish} disabled={saving}>
        <Text style={styles.primaryText}>{saving ? "Publishing…" : "Publish announcement"}</Text>
      </Pressable>
    </View>
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
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function publish() {
    const parsed = new Date(startsAt);
    if (!title.trim() || Number.isNaN(parsed.getTime())) {
      setError("Enter a title and a valid date and time, for example 2026-12-24T18:00.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const created = await communityService.createEvent({
        title: title.trim(),
        description: description.trim() || undefined,
        scope_type: scopeType,
        scope_id: scopeId,
        starts_at: parsed.toISOString(),
        location: location.trim() || undefined,
      });
      await communityService.publishEvent(created.id);
      await onPublished();
      setTitle("");
      setDescription("");
      setStartsAt("");
      setLocation("");
    } catch (publishError) {
      setError(describeError(publishError, "The event could not be published in your scope."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>Publish a {scopeType} event</Text>
      {error ? <Text style={styles.formError}>{error}</Text> : null}
      <TextInput
        value={title}
        onChangeText={setTitle}
        style={styles.input}
        placeholder="Event title"
        maxLength={200}
      />
      <TextInput
        value={description}
        onChangeText={setDescription}
        style={[styles.input, styles.multiline]}
        placeholder="Description"
        multiline
        maxLength={10000}
      />
      <TextInput
        value={startsAt}
        onChangeText={setStartsAt}
        style={styles.input}
        placeholder="Date and time, e.g. 2026-12-24T18:00"
      />
      <TextInput
        value={location}
        onChangeText={setLocation}
        style={styles.input}
        placeholder="Location"
        maxLength={255}
      />
      <Pressable style={styles.primaryButton} onPress={publish} disabled={saving}>
        <Text style={styles.primaryText}>{saving ? "Publishing…" : "Publish event"}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#F7F9F7" },
  content: { padding: 18, paddingBottom: 44 },
  title: { fontSize: 27, fontWeight: "800", color: "#0B6623" },
  subtitle: { color: "#59665C", lineHeight: 21, marginTop: 6 },
  card: {
    backgroundColor: "#fff",
    padding: 14,
    borderRadius: 12,
    borderColor: "#E3EAE4",
    borderWidth: 1,
    marginBottom: 9,
    gap: 6,
  },
  badge: { color: "#0B6623", fontWeight: "800", fontSize: 11 },
  cardTitle: { fontWeight: "700", fontSize: 16, color: "#1D3C25" },
  body: { color: "#39463C", lineHeight: 20 },
  cardMeta: { color: "#788279", fontSize: 12, lineHeight: 18 },
  reply: {
    backgroundColor: "#F2F6F3",
    borderRadius: 8,
    padding: 10,
    marginTop: 6,
  },
  input: {
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: "#D5DED7",
    borderRadius: 10,
    padding: 12,
    marginTop: 7,
  },
  multiline: { minHeight: 82, textAlignVertical: "top" },
  primaryButton: {
    backgroundColor: "#0B6623",
    padding: 12,
    alignItems: "center",
    borderRadius: 9,
    marginTop: 9,
  },
  primaryText: { color: "#fff", fontWeight: "700" },
  secondaryButton: {
    backgroundColor: "#EAF2EC",
    padding: 12,
    borderRadius: 9,
    marginTop: 9,
    alignItems: "center",
    flexGrow: 1,
  },
  secondaryText: { color: "#0B6623", fontWeight: "700" },
  linkButton: { paddingVertical: 6 },
  linkText: { color: "#0B6623", fontWeight: "700", fontSize: 13 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 7, marginTop: 8 },
  chip: {
    borderColor: "#B8C8BB",
    borderWidth: 1,
    borderRadius: 18,
    paddingHorizontal: 10,
    paddingVertical: 7,
  },
  chipSelected: { backgroundColor: "#0B6623", borderColor: "#0B6623" },
  chipText: { color: "#35513C", fontSize: 12, fontWeight: "600" },
  chipTextSelected: { color: "#fff" },
  switchRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 8,
  },
  row: { flexDirection: "row", gap: 8, alignItems: "center", flexWrap: "wrap" },
  rowBetween: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 10,
    paddingVertical: 6,
  },
  flex: { flex: 1 },
  notice: {
    color: "#1B4A2A",
    backgroundColor: "#EDF3EE",
    padding: 12,
    borderRadius: 10,
    marginTop: 12,
    lineHeight: 20,
  },
  formError: { color: "#8A1C13", marginTop: 10, lineHeight: 20 },
});