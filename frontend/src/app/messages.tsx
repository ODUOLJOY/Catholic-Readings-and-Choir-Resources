import React, { useCallback, useEffect, useState } from "react";
import {
  Alert,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";
import { router } from "expo-router";

import { ReportFormPayload, ReportModal } from "@/components/ReportModal";
import { EmptyState, ErrorState, LoadingState, SectionHeading } from "@/components/ScreenStates";
import {
  BlockEntry,
  CommunityMember,
  CommunityMessage,
  communityService,
  conversationLabel,
  ConversationSummary,
  describeError,
  MESSAGE_REACTIONS,
  MessageReactionSummary,
  ReportResult,
  reportMessageLabels,
} from "@/services/communityService";
import { authService } from "@/services/authService";

const PAGE_SIZE = 50;

type Thread = {
  summary: ConversationSummary | null;
  messages: CommunityMessage[];
  hasMore: boolean;
};

export default function MessagesScreen() {
  const [currentUserId, setCurrentUserId] = useState<number | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversationError, setConversationError] = useState<string | null>(null);
  const [conversationsLoading, setConversationsLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [members, setMembers] = useState<CommunityMember[]>([]);
  const [memberQuery, setMemberQuery] = useState("");
  const [memberError, setMemberError] = useState<string | null>(null);

  const [thread, setThread] = useState<Thread>({
    summary: null,
    messages: [],
    hasMore: false,
  });
  const [threadLoading, setThreadLoading] = useState(false);
  const [threadError, setThreadError] = useState<string | null>(null);
  const [loadingOlder, setLoadingOlder] = useState(false);

  const [draft, setDraft] = useState("");
  const [replyTo, setReplyTo] = useState<CommunityMessage | null>(null);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  const [blocks, setBlocks] = useState<BlockEntry[]>([]);
  const [reactions, setReactions] = useState<Record<number, MessageReactionSummary>>({});
  const [editing, setEditing] = useState<CommunityMessage | null>(null);
  const [editDraft, setEditDraft] = useState("");
  const [reporting, setReporting] = useState<CommunityMessage | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const blockedIds = new Set(blocks.map((entry) => entry.user_id));

  const loadConversations = useCallback(async (options?: { silent?: boolean }) => {
    if (options?.silent) {
      setRefreshing(true);
    } else {
      setConversationsLoading(true);
    }
    setConversationError(null);
    try {
      const list = await communityService.getConversations({ limit: PAGE_SIZE });
      setConversations(list);
    } catch (error) {
      setConversationError(
        describeError(error, "Your conversations could not be loaded. Please try again."),
      );
    } finally {
      setConversationsLoading(false);
      setRefreshing(false);
    }
  }, []);

  const loadBlocks = useCallback(async () => {
    try {
      const result = await communityService.getBlocks();
      setBlocks([...result.blocked, ...result.blocked_me]);
    } catch {
      // Blocking state only gates optional actions; a failure here must not block
      // reading conversations, so it is intentionally silent.
    }
  }, []);

  const loadReactions = useCallback(async (messageId: number) => {
    try {
      const summary = await communityService.getMessageReactions(messageId);
      setReactions((current) => ({ ...current, [messageId]: summary }));
    } catch {
      // Reaction counts are supplementary; a failure leaves the message usable.
    }
  }, []);

  useEffect(() => {
    let active = true;
    (async () => {
      const user = await authService.getUser();
      if (active) {
        setCurrentUserId(typeof user?.id === "number" ? user.id : null);
      }
      await Promise.all([loadConversations(), loadBlocks()]);
    })();

    return () => {
      active = false;
    };
  }, [loadConversations, loadBlocks]);

  useEffect(() => {
    if (!thread.messages.length) return;
    // Only the visible tail is hydrated, so opening a long thread does not issue
    // one request per message in the history.
    thread.messages.slice(-10).forEach((message) => {
      if (!reactions[message.id]) {
        void loadReactions(message.id);
      }
    });
  }, [thread.messages, reactions, loadReactions]);

  async function openConversation(summary: ConversationSummary) {
    setThread({ summary, messages: [], hasMore: false });
    setThreadError(null);
    setSendError(null);
    setReplyTo(null);
    setThreadLoading(true);
    try {
      const page = await communityService.getMessages(summary.id, { limit: PAGE_SIZE });
      setThread({ summary, messages: page, hasMore: page.length >= PAGE_SIZE });
      await communityService.markRead(summary.id);
      setConversations((current) =>
        current.map((item) =>
          item.id === summary.id ? { ...item, unread_count: 0 } : item,
        ),
      );
    } catch (error) {
      setThreadError(
        describeError(error, "This conversation could not be opened."),
      );
      setThread({ summary, messages: [], hasMore: false });
    } finally {
      setThreadLoading(false);
    }
  }

  async function loadOlderMessages() {
    const conversationId = thread.summary?.id;
    if (!conversationId || loadingOlder) return;
    const oldest = thread.messages[0];
    if (!oldest) return;

    setLoadingOlder(true);
    try {
      const older = await communityService.getMessages(conversationId, {
        beforeId: oldest.id,
        limit: PAGE_SIZE,
      });
      setThread((current) => ({
        ...current,
        messages: [...older, ...current.messages],
        hasMore: older.length >= PAGE_SIZE,
      }));
    } catch (error) {
      setThreadError(describeError(error, "Earlier messages could not be loaded."));
    } finally {
      setLoadingOlder(false);
    }
  }

  async function startDirect(member: CommunityMember) {
    if (busy) return;
    setBusy(true);
    setMemberError(null);
    try {
      if (blockedIds.has(member.id)) {
        setMemberError(
          `${member.full_name} cannot be messaged until the block is removed.`,
        );
        return;
      }
      const summary = await communityService.startDirectConversation(member.id);
      setConversations((current) => [
        summary,
        ...current.filter((item) => item.id !== summary.id),
      ]);
      await openConversation(summary);
    } catch (error) {
      setMemberError(
        describeError(error, "That conversation could not be started."),
      );
    } finally {
      setBusy(false);
    }
  }

  async function searchMembers() {
    setMemberError(null);
    try {
      const results = await communityService.searchMembers(
        memberQuery.trim() || undefined,
      );
      setMembers(results);
    } catch (error) {
      setMemberError(describeError(error, "The member list is unavailable."));
    }
  }

  async function send() {
    const conversationId = thread.summary?.id;
    const body = draft.trim();
    if (!conversationId || !body || sending) return;

    setSending(true);
    setSendError(null);
    try {
      const created = await communityService.sendMessage(
        conversationId,
        body,
        replyTo?.id,
      );
      setThread((current) => ({
        ...current,
        messages: [...current.messages, created],
      }));
      setConversations((current) =>
        current.map((item) =>
          item.id === conversationId
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
      setReplyTo(null);
    } catch (error) {
      // The draft is deliberately preserved so a rate-limited or offline failure
      // does not discard what the member typed.
      setSendError(
        describeError(error, "Your message was not sent. It is still in the box below."),
      );
    } finally {
      setSending(false);
    }
  }

  async function saveEdit() {
    if (!editing) return;
    const body = editDraft.trim();
    if (!body) {
      setActionError("A message cannot be edited to be empty.");
      return;
    }
    setBusy(true);
    setActionError(null);
    try {
      const updated = await communityService.editMessage(editing.id, body);
      setThread((current) => ({
        ...current,
        messages: current.messages.map((message) =>
          message.id === updated.id ? { ...updated, is_edited: true } : message,
        ),
      }));
      setEditing(null);
      setEditDraft("");
    } catch (error) {
      setActionError(describeError(error, "The message could not be edited."));
    } finally {
      setBusy(false);
    }
  }

  async function remove(message: CommunityMessage) {
    if (busy) return;
    setBusy(true);
    setActionError(null);
    try {
      await communityService.deleteMessage(message.id);
      setThread((current) => ({
        ...current,
        messages: current.messages.filter((item) => item.id !== message.id),
      }));
    } catch (error) {
      setActionError(describeError(error, "The message could not be deleted."));
    } finally {
      setBusy(false);
    }
  }

  async function toggleReaction(message: CommunityMessage, reaction: string, mine: boolean) {
    setActionError(null);
    try {
      if (mine) {
        await communityService.removeMessageReaction(message.id, reaction);
      } else {
        await communityService.addMessageReaction(message.id, reaction);
      }
      await loadReactions(message.id);
    } catch (error) {
      setActionError(describeError(error, "Your reaction could not be saved."));
    }
  }

  async function toggleMute(summary: ConversationSummary) {
    const next = !summary.is_muted;
    setConversations((current) =>
      current.map((item) =>
        item.id === summary.id ? { ...item, is_muted: next } : item,
      ),
    );
    try {
      await communityService.setConversationMuted(summary.id, next);
    } catch (error) {
      setConversationError(describeError(error, "The mute setting could not be saved."));
      setConversations((current) =>
        current.map((item) =>
          item.id === summary.id ? { ...item, is_muted: summary.is_muted } : item,
        ),
      );
    }
  }

  async function blockParticipant() {
    const participant = thread.summary?.participant;
    if (!participant) return;
    setBusy(true);
    setActionError(null);
    try {
      await communityService.blockMember(participant.id);
      await loadBlocks();
      Alert.alert(
        "Member blocked",
        `${participant.full_name} can no longer message you, and this conversation is hidden.`,
      );
      setThread({ summary: null, messages: [], hasMore: false });
      await loadConversations({ silent: true });
    } catch (error) {
      setActionError(describeError(error, "That member could not be blocked."));
    } finally {
      setBusy(false);
    }
  }

  const unblocking = blocks.find(
    (entry) => entry.direction === "blocked_by_me" && thread.summary?.participant?.id === entry.user_id,
  );

  async function unblockParticipant() {
    if (!unblocking) return;
    setBusy(true);
    setActionError(null);
    try {
      await communityService.unblockMember(unblocking.user_id);
      await loadBlocks();
      await loadConversations({ silent: true });
    } catch (error) {
      setActionError(describeError(error, "That member could not be unblocked."));
    } finally {
      setBusy(false);
    }
  }

  async function submitMessageReport(payload: ReportFormPayload): Promise<ReportResult> {
    if (!reporting) {
      throw new Error("Select a message to report before submitting.");
    }
    return communityService.reportMessage(reporting.id, payload);
  }

  if (conversationsLoading && !conversations.length) {
    return <LoadingState label="Loading your conversations…" />;
  }

  return (
    <KeyboardAvoidingView
      style={styles.screen}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Text style={styles.title}>Messages</Text>
        <Text style={styles.help}>
          Direct messages are limited to verified members of your own parish community and are never
          visible to other parishes. Reactions, edits, blocking and reporting are enforced on the
          server.
        </Text>

        {conversationError ? (
          <ErrorState
            message={conversationError}
            onRetry={() => void loadConversations()}
          />
        ) : null}

        <SectionHeading>Start a direct message</SectionHeading>
        <View style={styles.searchRow}>
          <TextInput
            value={memberQuery}
            onChangeText={setMemberQuery}
            style={[styles.input, styles.searchInput]}
            placeholder="Search parish members by name"
            maxLength={100}
          />
          <Pressable style={styles.primaryButton} onPress={searchMembers} disabled={busy}>
            <Text style={styles.primaryText}>Search</Text>
          </Pressable>
        </View>
        {memberError ? <Text style={styles.inlineError}>{memberError}</Text> : null}
        {members.length === 0 ? (
          <EmptyState message="No verified parish members are available to message." />
        ) : (
          <View style={styles.chips}>
            {members.map((member) => (
              <Pressable
                key={member.id}
                style={styles.chip}
                onPress={() => void startDirect(member)}
                disabled={busy}
              >
                <Text style={styles.chipText}>{member.full_name}</Text>
              </Pressable>
            ))}
          </View>
        )}

        <SectionHeading>Conversations</SectionHeading>
        {refreshing ? (
          <Text style={styles.metaRefreshing}>Refreshing…</Text>
        ) : null}
        {conversations.length === 0 ? (
          <EmptyState message="You have no conversations yet. Start one with a parish member above." />
        ) : (
          conversations.map((summary) => (
            <View
              key={summary.id}
              style={[styles.card, thread.summary?.id === summary.id && styles.cardActive]}
            >
              <Pressable onPress={() => void openConversation(summary)}>
                <View style={styles.cardHeader}>
                  <Text style={styles.cardTitle}>
                    {conversationLabel(summary)}
                  </Text>
                  {summary.unread_count > 0 ? (
                    <View style={styles.badge}>
                      <Text style={styles.badgeText}>{summary.unread_count}</Text>
                    </View>
                  ) : null}
                </View>
                <Text style={styles.preview} numberOfLines={2}>
                  {summary.last_message?.body ?? "No messages yet."}
                </Text>
                <Text style={styles.cardMeta}>
                  {summary.conversation_type === "direct"
                    ? "Private conversation"
                    : `Scoped conversation · ${summary.unread_count} unread`}
                  {summary.is_muted ? " · Muted" : ""}
                </Text>
              </Pressable>
              <View style={styles.cardActions}>
                <View style={styles.muteRow}>
                  <Text style={styles.muteLabel}>Mute</Text>
                  <Switch
                    value={summary.is_muted}
                    onValueChange={() => void toggleMute(summary)}
                    trackColor={{ true: "#0B6623" }}
                  />
                </View>
                {summary.participant ? (
                  <Pressable
                    style={styles.linkButton}
                    onPress={() =>
                      router.push({
                        pathname: "/report-content",
                        params: {
                          resourceType: "user_profile",
                          resourceId: String(summary.participant?.id ?? ""),
                        },
                      })
                    }
                  >
                    <Text style={styles.linkText}>Report profile</Text>
                  </Pressable>
                ) : null}
              </View>
            </View>
          ))
        )}

        {actionError ? (
          <ErrorState
            message={actionError}
            onRetry={() => setActionError(null)}
            retryLabel="Dismiss"
          />
        ) : null}

        {thread.summary ? (
          <View style={styles.thread}>
            <Text style={styles.threadTitle}>
              {conversationLabel(thread.summary)}
            </Text>
            <View style={styles.threadHeaderActions}>
              {thread.summary.participant ? (
                blockedIds.has(thread.summary.participant.id) ? (
                  <Pressable style={styles.secondaryButton} onPress={unblockParticipant}>
                    <Text style={styles.secondaryText}>Unblock member</Text>
                  </Pressable>
                ) : (
                  <Pressable style={styles.dangerButton} onPress={blockParticipant}>
                    <Text style={styles.secondaryText}>Block member</Text>
                  </Pressable>
                )
              ) : null}
            </View>

            {threadLoading ? (
              <LoadingState label="Opening conversation…" />
            ) : threadError ? (
              <ErrorState
                message={threadError}
                onRetry={() => void openConversation(thread.summary as ConversationSummary)}
              />
            ) : (
              <>
                {thread.hasMore ? (
                  <Pressable style={styles.linkButton} onPress={loadOlderMessages}>
                    <Text style={styles.linkText}>
                      {loadingOlder ? "Loading…" : "Load earlier messages"}
                    </Text>
                  </Pressable>
                ) : null}
                {thread.messages.length === 0 ? (
                  <EmptyState message="This conversation has no messages yet." />
                ) : (
                  thread.messages.map((message) => {
                    const mine = message.sender_id === currentUserId;
                    const reactionSummary = reactions[message.id];
                    return (
                      <View
                        key={message.id}
                        style={[styles.message, mine ? styles.messageMine : styles.messageTheirs]}
                      >
                        {message.reply_to_id ? (
                          <Text style={styles.messageMeta}>In reply to a message above</Text>
                        ) : null}
                        <Text style={styles.body}>{message.body}</Text>
                        <Text style={styles.messageMeta}>
                          {new Date(message.created_at).toLocaleString()}
                          {message.is_edited ? " · edited" : ""}
                        </Text>
                        <View style={styles.reactions}>
                          {MESSAGE_REACTIONS.map((option) => {
                            const count =
                              reactionSummary?.counts?.[option.key] ?? 0;
                            const active =
                              reactionSummary?.mine?.includes(option.key) ?? false;
                            // Show reactions that already exist, plus the "add reaction"
                            // affordance whenever the member has not reacted yet.
                            if (count === 0 && !active && reactionSummary) return null;
                            return (
                              <Pressable
                                key={option.key}
                                style={[
                                  styles.reactionChip,
                                  active && styles.reactionChipActive,
                                  reactionSummary ? undefined : styles.reactionChipMuted,
                                ]}
                                onPress={() =>
                                  void toggleReaction(message, option.key, active)
                                }
                              >
                                <Text
                                  style={[styles.reactionText, active && styles.reactionTextActive]}
                                >
                                  {option.label} {count > 0 ? count : ""}
                                </Text>
                              </Pressable>
                            );
                          })}
                        </View>
                        <View style={styles.messageActions}>
                          <Pressable
                            style={styles.linkButton}
                            onPress={() => setReplyTo(message)}
                          >
                            <Text style={styles.linkText}>Reply</Text>
                          </Pressable>
                          {mine ? (
                            <>
                              <Pressable
                                style={styles.linkButton}
                                onPress={() => {
                                  setEditing(message);
                                  setEditDraft(message.body);
                                }}
                              >
                                <Text style={styles.linkText}>Edit</Text>
                              </Pressable>
                              <Pressable
                                style={styles.linkButton}
                                onPress={() => void remove(message)}
                              >
                                <Text style={styles.linkText}>Delete</Text>
                              </Pressable>
                            </>
                          ) : (
                            <Pressable
                              style={styles.linkButton}
                              onPress={() => setReporting(message)}
                            >
                              <Text style={styles.linkText}>Report</Text>
                            </Pressable>
                          )}
                        </View>
                      </View>
                    );
                  })
                )}
              </>
            )}

            <View style={styles.composer}>
              {replyTo ? (
                <View style={styles.replyBanner}>
                  <Text style={styles.messageMeta} numberOfLines={2}>
                    Replying to: {replyTo.body}
                  </Text>
                  <Pressable style={styles.linkButton} onPress={() => setReplyTo(null)}>
                    <Text style={styles.linkText}>Cancel reply</Text>
                  </Pressable>
                </View>
              ) : null}
              <TextInput
                value={draft}
                onChangeText={setDraft}
                style={[styles.input, styles.multiline]}
                placeholder="Write a message"
                maxLength={10000}
                multiline
              />
              {sendError ? <Text style={styles.inlineError}>{sendError}</Text> : null}
              <Pressable style={styles.primaryButton} onPress={send} disabled={sending}>
                <Text style={styles.primaryText}>
                  {sending ? "Sending…" : "Send message"}
                </Text>
              </Pressable>
            </View>
          </View>
        ) : null}
      </ScrollView>

      <Modal
        visible={editing !== null}
        transparent
        animationType="slide"
        onRequestClose={() => setEditing(null)}
      >
        <View style={styles.backdrop}>
          <View style={styles.sheet}>
            <Text style={styles.sheetTitle}>Edit message</Text>
            <TextInput
              value={editDraft}
              onChangeText={setEditDraft}
              style={[styles.input, styles.multiline]}
              multiline
              maxLength={10000}
            />
            {actionError ? <Text style={styles.inlineError}>{actionError}</Text> : null}
            <Pressable style={styles.primaryButton} onPress={saveEdit} disabled={busy}>
              <Text style={styles.primaryText}>Save edit</Text>
            </Pressable>
            <Pressable style={styles.secondaryButton} onPress={() => setEditing(null)}>
              <Text style={styles.secondaryText}>Cancel</Text>
            </Pressable>
          </View>
        </View>
      </Modal>

      {reporting ? (
        <ReportModal
          visible
          onClose={() => setReporting(null)}
          resourceType="message"
          resourceId={reporting.id}
          onSubmit={submitMessageReport}
          labels={reportMessageLabels}
          title="Report message"
        />
      ) : null}
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#F7F9F7" },
  content: { padding: 18, paddingBottom: 48 },
  title: { fontSize: 27, fontWeight: "800", color: "#0B6623" },
  help: { color: "#59665C", lineHeight: 21, marginTop: 6 },
  searchRow: { flexDirection: "row", gap: 8, alignItems: "center" },
  searchInput: { flex: 1 },
  input: {
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: "#D5DED7",
    borderRadius: 10,
    padding: 12,
    marginTop: 7,
  },
  multiline: { minHeight: 74, textAlignVertical: "top" },
  primaryButton: {
    backgroundColor: "#0B6623",
    paddingHorizontal: 16,
    paddingVertical: 13,
    borderRadius: 10,
    alignItems: "center",
    marginTop: 8,
  },
  primaryText: { color: "#fff", fontWeight: "700" },
  secondaryButton: {
    backgroundColor: "#EAF2EC",
    padding: 12,
    borderRadius: 9,
    marginTop: 9,
    alignItems: "center",
  },
  secondaryText: { color: "#0B6623", fontWeight: "700" },
  dangerButton: {
    backgroundColor: "#A52A2A",
    padding: 12,
    borderRadius: 9,
    marginTop: 9,
    alignItems: "center",
  },
  linkButton: { paddingVertical: 6, paddingRight: 14 },
  linkText: { color: "#0B6623", fontWeight: "700", fontSize: 13 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 10 },
  chip: {
    borderWidth: 1,
    borderColor: "#B8C8BB",
    borderRadius: 18,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  chipText: { color: "#28412F", fontWeight: "600" },
  card: {
    backgroundColor: "#fff",
    padding: 14,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#E4EAE5",
    marginBottom: 9,
  },
  cardActive: { borderColor: "#0B6623" },
  cardHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  cardTitle: { color: "#1D3C25", fontWeight: "700", fontSize: 16, flex: 1 },
  preview: { color: "#66736A", marginTop: 6 },
  cardMeta: { color: "#7A847D", fontSize: 12, marginTop: 6 },
  cardActions: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  muteRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  muteLabel: { color: "#4B5A50", fontSize: 13 },
  badge: {
    backgroundColor: "#C62828",
    borderRadius: 10,
    minWidth: 20,
    paddingHorizontal: 6,
    paddingVertical: 2,
    alignItems: "center",
  },
  badgeText: { color: "#fff", fontWeight: "700", fontSize: 12 },
  metaRefreshing: { color: "#7A847D", fontSize: 12, marginBottom: 6 },
  inlineError: { color: "#8A1C13", marginTop: 8, lineHeight: 20 },
  thread: {
    marginTop: 18,
    padding: 12,
    backgroundColor: "#EDF3EE",
    borderRadius: 12,
  },
  threadTitle: { fontSize: 18, fontWeight: "700", color: "#183D24" },
  threadHeaderActions: { flexDirection: "row", gap: 8, marginTop: 6 },
  message: { borderRadius: 10, marginBottom: 8, padding: 10, maxWidth: "94%" },
  messageMine: { alignSelf: "flex-end", backgroundColor: "#DCEBE0" },
  messageTheirs: { alignSelf: "flex-start", backgroundColor: "#fff" },
  body: { color: "#39463C", lineHeight: 20 },
  messageMeta: { color: "#788279", marginTop: 4, fontSize: 12 },
  reactions: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 8 },
  reactionChip: {
    borderWidth: 1,
    borderColor: "#B8C8BB",
    borderRadius: 14,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  reactionChipActive: { backgroundColor: "#0B6623", borderColor: "#0B6623" },
  reactionChipMuted: { opacity: 0.55, borderStyle: "dashed" },
  reactionText: { color: "#35513C", fontSize: 12, fontWeight: "600" },
  reactionTextActive: { color: "#fff" },
  messageActions: { flexDirection: "row", flexWrap: "wrap", marginTop: 4 },
  composer: { marginTop: 10 },
  replyBanner: {
    backgroundColor: "#fff",
    borderRadius: 10,
    padding: 10,
    marginBottom: 4,
  },
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(10, 26, 15, 0.55)",
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: "#fff",
    borderTopLeftRadius: 18,
    borderTopRightRadius: 18,
    padding: 18,
    paddingBottom: 28,
  },
  sheetTitle: { fontSize: 20, fontWeight: "800", color: "#0B6623", marginBottom: 6 },
});