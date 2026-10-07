import { isAxiosError } from "axios";

import { api } from "@/lib/api";
import { detailMessage } from "@/lib/requestFailure";

/**
 * Single authoritative client for the community, messaging, suggestion,
 * moderation and reporting surfaces. Every community screen goes through this
 * module so request shapes cannot drift between screens or fall back to ad hoc
 * `api.get(...)` calls that are never updated when the backend contract moves.
 */

export type ScopeType = "parish" | "diocese" | "group";

export type ConversationSummary = {
  id: number;
  conversation_type: "scope" | "direct";
  scope_type: string | null;
  scope_id: number | null;
  group_id: number | null;
  created_by: number;
  created_at: string;
  unread_count: number;
  is_muted: boolean;
  last_message: {
    id: number;
    sender_id: number;
    body: string;
    created_at: string;
  } | null;
  participant?: {
    id: number;
    full_name: string;
  } | null;
};

export type CommunityMessage = {
  id: number;
  conversation_id: number;
  sender_id: number;
  reply_to_id: number | null;
  body: string;
  is_edited: boolean;
  edited_at: string | null;
  created_at: string;
};

export type CommunityMember = {
  id: number;
  full_name: string;
  parish_id: number | null;
};

export type MessageReactionSummary = {
  message_id: number;
  counts: Record<string, number>;
  mine: string[];
};

export type BlockEntry = {
  user_id: number;
  full_name: string;
  direction: "blocked_by_me" | "blocked_me";
};

export type CommunityHeader = {
  community: {
    parish_id: number;
    parish_name: string;
    parish_code: string | null;
    diocese_id: number | null;
    diocese_name: string | null;
    deanery_id: number | null;
    deanery_name: string | null;
    member_count: number;
    description: string | null;
    rules: string;
    conversation_id: number | null;
    my_roles: { role: string; scope_type: string; scope_id: number; ministry: string | null }[];
    can_moderate: boolean;
    can_manage: boolean;
  } | null;
  parish_membership_status: string | null;
  rules: string;
  unavailable_reason?: string;
};

export type CommunityRole = {
  id?: number;
  role: string;
  scope_type: string;
  scope_id: number | null;
  ministry?: string | null;
};

export type CommunityProfile = {
  parish_id: number | null;
  parish_name: string | null;
  diocese_id: number | null;
  diocese_name: string | null;
  deanery_id: number | null;
  deanery_name: string | null;
  roles: CommunityRole[];
  pending_role_requests: number;
  parish_membership_status: string | null;
};

export type CommunityAnnouncement = {
  id: number;
  title: string;
  body: string;
  announcement_type: string;
  audience_type: string;
  audience_id: number | null;
  created_at?: string;
};

export type CommunityEvent = {
  id: number;
  title: string;
  description?: string | null;
  starts_at: string;
  location?: string | null;
  is_published?: boolean;
};

export type PrayerIntention = {
  id: number;
  intention: string;
  visibility: string;
  created_at?: string;
  is_mine: boolean;
};

export type PrayerVisibility = "private" | "parish" | "diocese" | "public";

export type SuggestionReply = {
  id: number;
  author_id: number;
  body: string;
  is_internal: boolean | null;
  created_at: string;
};

export type SuggestionStatus =
  | "submitted"
  | "under_review"
  | "needs_information"
  | "in_discussion"
  | "accepted"
  | "escalated"
  | "implemented"
  | "declined"
  | "archived";

export type SuggestionSummary = {
  id: number;
  category: string;
  body: string;
  scope_type: string;
  scope_id: number;
  status: SuggestionStatus;
  is_anonymous: boolean;
  submitter_id?: number | null;
  assigned_to?: number | null;
  escalated_at?: string | null;
  review_note?: string | null;
  created_at?: string;
};

export type SuggestionDetail = SuggestionSummary & {
  submitter_name: string | null;
  resolved_at: string | null;
  replies: SuggestionReply[];
  can_manage: boolean;
};

export type MembershipRequest = {
  id: number;
  user_id: number;
  full_name: string;
  email: string;
  parish_id: number;
  parish_name: string;
  status: string;
  requested_at: string;
  review_note?: string | null;
};

export type CommunityGroupSummary = {
  id: number;
  name: string;
  scope_type: ScopeType;
  scope_id: number;
  description?: string | null;
  is_active?: boolean;
  category?: string | null;
};

export type RoleAssignmentView = {
  assignment_id: number;
  user_id: number;
  full_name: string;
  email: string;
  role: string;
  scope_type: string;
  scope_id: number | null;
  ministry?: string | null;
};

export type RoleRequestView = {
  id: number;
  requester_id?: number;
  requested_role: string;
  scope_type: string;
  scope_id: number;
  ministry?: string | null;
  reason: string;
  status: string;
  review_note?: string | null;
  created_at?: string;
};

export type CommunityAuditRecord = {
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

export type NotificationPreferences = {
  announcements: boolean;
  events: boolean;
  role_requests: boolean;
  messages: boolean;
};

export type ReportableResourceType =
  | "reading"
  | "saint"
  | "choir"
  | "choir_resource"
  | "message"
  | "announcement"
  | "suggestion"
  | "group"
  | "event"
  | "prayer_intention"
  | "user_profile";

export type ReportCategory =
  | "spam"
  | "harassment"
  | "abusive_language"
  | "inappropriate_content"
  | "misleading_information"
  | "suspicious_activity"
  | "copyright"
  | "other";

export type ReportResult = {
  message?: string;
  report_id: number;
  status: string;
  category?: string;
  duplicate?: boolean;
};

/** Wording shared by every reporting surface so members see one voice. */
export type ReportFormLabels = {
  title: string;
  intro: string;
  reasonPlaceholder: string;
  descriptionPlaceholder: string;
  submitLabel: string;
  submittingLabel: string;
};

export const defaultReportLabels: ReportFormLabels = {
  title: "Report content",
  intro:
    "A moderator reviews every report. Your name is not shown to the member being reported.",
  reasonPlaceholder: "What is wrong with this content?",
  descriptionPlaceholder: "Anything else a moderator should know",
  submitLabel: "Submit report",
  submittingLabel: "Submitting…",
};

export const reportMessageLabels: ReportFormLabels = {
  title: "Report message",
  intro:
    "A moderator reviews every report. The member who sent this message is not told who reported it.",
  reasonPlaceholder: "What is wrong with this message?",
  descriptionPlaceholder: "Anything else a moderator should know",
  submitLabel: "Report message",
  submittingLabel: "Reporting…",
};

/**
 * Human label for a conversation row. Direct threads use the other member's
 * name; scoped threads are labelled by their organizational scope because that
 * is what the member was authorized to see.
 */
export function conversationLabel(summary: ConversationSummary): string {
  if (summary.conversation_type === "direct") {
    return summary.participant?.full_name ?? "Direct message";
  }
  if (summary.scope_type && summary.scope_id) {
    return `${summary.scope_type.charAt(0).toUpperCase()}${summary.scope_type.slice(1)} conversation`;
  }
  return `Conversation #${summary.id}`;
}

/**
 * Mirrors `SUGGESTION_CATEGORIES` in `backend/app/routes/community.py`. The
 * backend validates the value regardless; the local list only spares a member a
 * round trip for an obviously invalid category.
 */
export const SUGGESTION_CATEGORIES: { key: string; label: string }[] = [
  { key: "liturgy", label: "Liturgy" },
  { key: "youth", label: "Youth" },
  { key: "choir_music", label: "Choir/Music" },
  { key: "catechesis", label: "Catechesis" },
  { key: "parish_activities", label: "Parish activities" },
  { key: "charity", label: "Charity" },
  { key: "evangelization", label: "Evangelization" },
  { key: "technology", label: "Technology" },
  { key: "community", label: "Community" },
  { key: "other", label: "Other" },
];

/** Mirrors `REPORT_CATEGORIES` in the reporting router. */
export const REPORT_CATEGORIES: { key: ReportCategory; label: string }[] = [
  { key: "harassment", label: "Harassment" },
  { key: "abusive_language", label: "Abusive language" },
  { key: "spam", label: "Spam" },
  { key: "inappropriate_content", label: "Inappropriate content" },
  { key: "misleading_information", label: "Misleading information" },
  { key: "suspicious_activity", label: "Suspicious activity" },
  { key: "copyright", label: "Copyright concern" },
  { key: "other", label: "Other" },
];

/**
 * Mirrors `SUGGESTION_TRANSITIONS` in the community router. Only transitions the
 * server accepts are offered, so an administrator is never shown an action that
 * is guaranteed to fail with 409.
 */
export const SUGGESTION_TRANSITIONS: Record<SuggestionStatus, SuggestionStatus[]> = {
  submitted: [
    "under_review",
    "needs_information",
    "in_discussion",
    "accepted",
    "declined",
    "escalated",
    "archived",
  ],
  under_review: [
    "needs_information",
    "in_discussion",
    "accepted",
    "declined",
    "escalated",
    "archived",
  ],
  in_discussion: [
    "under_review",
    "needs_information",
    "accepted",
    "declined",
    "escalated",
    "archived",
  ],
  needs_information: [
    "under_review",
    "in_discussion",
    "accepted",
    "declined",
    "escalated",
    "archived",
  ],
  accepted: ["in_discussion", "implemented", "declined", "escalated", "archived"],
  escalated: [
    "under_review",
    "in_discussion",
    "accepted",
    "implemented",
    "declined",
    "archived",
  ],
  implemented: [],
  declined: [],
  archived: [],
};

/** Statuses the backend refuses without an explicit `review_note`. */
export const SUGGESTION_STATUSES_REQUIRING_NOTE: SuggestionStatus[] = [
  "needs_information",
  "declined",
  "archived",
];

export const SUGGESTION_STATUS_LABELS: Record<SuggestionStatus, string> = {
  submitted: "Submitted",
  under_review: "Under review",
  needs_information: "Needs information",
  in_discussion: "In discussion",
  accepted: "Accepted",
  escalated: "Escalated",
  implemented: "Implemented",
  declined: "Declined",
  archived: "Archived",
};

/** Reaction vocabulary offered in the UI; the server stores a free string. */
export const MESSAGE_REACTIONS: { key: string; label: string }[] = [
  { key: "amen", label: "Amen" },
  { key: "praying", label: "Praying" },
  { key: "thanks", label: "Thanks" },
  { key: "agree", label: "Agree" },
];

const REPORTABLE_RESOURCE_TYPES: ReportableResourceType[] = [
  "reading",
  "saint",
  "choir",
  "choir_resource",
  "message",
  "announcement",
  "suggestion",
  "group",
  "event",
  "prayer_intention",
  "user_profile",
];

/**
 * Turn an API failure into a member-readable sentence. FastAPI returns either a
 * string `detail`, a validation array, or nothing at all, so all three shapes are
 * handled before falling back to the caller's own wording.
 *
 * The `detail` extraction is shared with `@/lib/requestFailure` so the two
 * cannot drift apart on the array shape.
 */
export function describeError(error: unknown, fallback: string): string {
  if (isAxiosError(error)) {
    if (!error.response) {
      return error.code === "ECONNABORTED"
        ? "The server took too long to respond. Please try again."
        : "No connection to the server. Check your network and try again.";
    }
    const detail = detailMessage(error);
    if (detail) {
      return detail;
    }
    if (error.response.status === 401) {
      return "Your session has expired or your account is no longer active. Sign in again to continue.";
    }
    if (error.response.status === 403) {
      return "You are not permitted to do that in your current scope.";
    }
    if (error.response.status === 404) {
      return "That content is no longer available.";
    }
    if (error.response.status === 409) {
      return "That action conflicts with the current state of this content.";
    }
    if (error.response.status === 429) {
      return "Too many requests. Wait a moment before trying again.";
    }
  }
  return fallback;
}

export function isReportableResourceType(value: string): value is ReportableResourceType {
  return (REPORTABLE_RESOURCE_TYPES as string[]).includes(value.trim().toLowerCase());
}

export const communityService = {
  // ---------------------------------------------------------------- identity
  async getHeader(): Promise<CommunityHeader> {
    const response = await api.get<CommunityHeader>("/api/community/header");
    return response.data;
  },

  async getProfile(): Promise<CommunityProfile> {
    const response = await api.get<CommunityProfile>("/api/community/me");
    return response.data;
  },

  // ----------------------------------------------------------- announcements
  async getAnnouncements(): Promise<CommunityAnnouncement[]> {
    const response = await api.get<CommunityAnnouncement[]>("/api/community/announcements");
    return response.data;
  },

  async createAnnouncement(payload: {
    title: string;
    body: string;
    announcement_type?: string;
    audience_type: ScopeType;
    audience_id: number;
  }): Promise<CommunityAnnouncement> {
    const response = await api.post<CommunityAnnouncement>("/api/community/announcements", {
      title: payload.title,
      body: payload.body,
      announcement_type: payload.announcement_type ?? "parish",
      audience_type: payload.audience_type,
      audience_id: payload.audience_id,
      status: "draft",
    });
    return response.data;
  },

  async publishAnnouncement(announcementId: number): Promise<void> {
    await api.post(`/api/community/announcements/${announcementId}/publish`);
  },

  // ------------------------------------------------------------------ events
  async getEvents(): Promise<CommunityEvent[]> {
    const response = await api.get<CommunityEvent[]>("/api/community/events");
    return response.data;
  },

  async createEvent(payload: {
    title: string;
    description?: string;
    scope_type: ScopeType;
    scope_id: number;
    starts_at: string;
    location?: string;
  }): Promise<CommunityEvent> {
    const response = await api.post<CommunityEvent>("/api/community/events", payload);
    return response.data;
  },

  async publishEvent(eventId: number): Promise<void> {
    await api.post(`/api/community/events/${eventId}/publish`);
  },

  // ------------------------------------------------------- prayer intentions
  async getPrayerIntentions(): Promise<PrayerIntention[]> {
    const response = await api.get<PrayerIntention[]>("/api/community/prayer-intentions");
    return response.data;
  },

  async createPrayerIntention(
    intention: string,
    visibility: PrayerVisibility,
  ): Promise<{ id: number; intention: string; visibility: string }> {
    const response = await api.post<{ id: number; intention: string; visibility: string }>(
      "/api/community/prayer-intentions",
      { intention, visibility },
    );
    return response.data;
  },

  async prayForIntention(intentionId: number): Promise<{ intention_id: number; status: string }> {
    const response = await api.post<{ intention_id: number; status: string }>(
      `/api/community/prayer-intentions/${intentionId}/reactions`,
      { reaction: "praying" },
    );
    return response.data;
  },

  // ------------------------------------------------------------- suggestions
  async createSuggestion(payload: {
    category: string;
    body: string;
    scope_type: "parish" | "diocese";
    scope_id: number;
    is_anonymous: boolean;
  }): Promise<SuggestionSummary> {
    const response = await api.post<SuggestionSummary>("/api/community/suggestions", payload);
    return response.data;
  },

  async getMySuggestions(): Promise<SuggestionSummary[]> {
    const response = await api.get<SuggestionSummary[]>("/api/community/suggestions/mine");
    return response.data;
  },

  async getSuggestionDetail(suggestionId: number): Promise<SuggestionDetail> {
    const response = await api.get<SuggestionDetail>(`/api/community/suggestions/${suggestionId}`);
    return response.data;
  },

  async replyToSuggestion(
    suggestionId: number,
    body: string,
    isInternal: boolean,
  ): Promise<SuggestionReply> {
    const response = await api.post<SuggestionReply>(
      `/api/community/suggestions/${suggestionId}/replies`,
      { body, is_internal: isInternal },
    );
    return response.data;
  },

  async getReviewQueue(): Promise<SuggestionSummary[]> {
    const response = await api.get<SuggestionSummary[]>("/api/community/suggestions/review");
    return response.data;
  },

  async updateSuggestion(
    suggestionId: number,
    status: SuggestionStatus,
    reviewNote?: string,
  ): Promise<SuggestionSummary> {
    const response = await api.patch<SuggestionSummary>(
      `/api/community/suggestions/${suggestionId}`,
      { status, review_note: reviewNote?.trim() || undefined },
    );
    return response.data;
  },

  // ------------------------------------------------------------- membership
  async requestMembership(): Promise<void> {
    await api.post("/api/community/memberships/request");
  },

  async getReviewableMemberships(): Promise<MembershipRequest[]> {
    const response = await api.get<MembershipRequest[]>("/api/community/memberships/review");
    return response.data;
  },

  async reviewMembership(
    membershipId: number,
    status: "active" | "rejected",
    reviewNote?: string,
  ): Promise<void> {
    await api.patch(`/api/community/memberships/${membershipId}`, {
      status,
      review_note: reviewNote?.trim() || undefined,
    });
  },

  // --------------------------------------------------------- role requests
  async getMyRoleRequests(): Promise<RoleRequestView[]> {
    const response = await api.get<RoleRequestView[]>("/api/community/role-requests/mine");
    return response.data;
  },

  async getReviewableRoleRequests(): Promise<RoleRequestView[]> {
    const response = await api.get<RoleRequestView[]>("/api/community/role-requests/review");
    return response.data;
  },

  async createRoleRequest(payload: {
    requested_role: string;
    scope_type: ScopeType;
    scope_id: number;
    ministry?: string;
    reason: string;
    supporting_information?: string;
  }): Promise<RoleRequestView> {
    const response = await api.post<RoleRequestView>("/api/community/role-requests", payload);
    return response.data;
  },

  async decideRoleRequest(
    requestId: number,
    status: "under_review" | "more_information_required" | "approved" | "rejected",
    reviewNote?: string,
  ): Promise<void> {
    await api.patch(`/api/community/role-requests/${requestId}`, {
      status,
      review_note: reviewNote?.trim() || undefined,
    });
  },

  // ---------------------------------------------------------- assignments
  async getAdministrators(): Promise<RoleAssignmentView[]> {
    const response = await api.get<RoleAssignmentView[]>("/api/community/administrators");
    return response.data;
  },

  async getMyGroups(): Promise<CommunityGroupSummary[]> {
    const response = await api.get<CommunityGroupSummary[]>("/api/community/groups/mine");
    return response.data;
  },

  async revokeRoleAssignment(assignmentId: number, reason: string): Promise<void> {
    await api.delete(`/api/community/role-assignments/${assignmentId}`, {
      params: { reason },
    });
  },

  // ------------------------------------------------------- conversations
  async getConversations(params?: { limit?: number; offset?: number }): Promise<ConversationSummary[]> {
    const response = await api.get<ConversationSummary[]>("/api/community/conversations", {
      params,
    });
    return response.data;
  },

  async getConversation(conversationId: number): Promise<ConversationSummary> {
    const response = await api.get<ConversationSummary>(
      `/api/community/conversations/${conversationId}`,
    );
    return response.data;
  },

  async openParishConversation(parishId: number): Promise<ConversationSummary> {
    const response = await api.post<ConversationSummary>("/api/community/conversations", {
      scope_type: "parish",
      scope_id: parishId,
    });
    return response.data;
  },

  async startDirectConversation(userId: number): Promise<ConversationSummary> {
    const response = await api.post<ConversationSummary>(
      "/api/community/conversations/direct",
      { user_id: userId },
    );
    return response.data;
  },

  async searchMembers(query?: string): Promise<CommunityMember[]> {
    const response = await api.get<CommunityMember[]>("/api/community/members", {
      params: query ? { q: query } : undefined,
    });
    return response.data;
  },

  /**
   * Messages are returned newest-first by the server; the service normalizes the
   * order so no screen has to remember to reverse them.
   */
  async getMessages(
    conversationId: number,
    params?: { beforeId?: number; limit?: number },
  ): Promise<CommunityMessage[]> {
    const response = await api.get<CommunityMessage[]>(
      `/api/community/conversations/${conversationId}/messages`,
      {
        params: {
          limit: params?.limit,
          before_id: params?.beforeId,
        },
      },
    );
    return [...response.data].reverse();
  },

  async sendMessage(
    conversationId: number,
    body: string,
    replyToId?: number,
  ): Promise<CommunityMessage> {
    const response = await api.post<CommunityMessage>(
      `/api/community/conversations/${conversationId}/messages`,
      { body, reply_to_id: replyToId },
    );
    return response.data;
  },

  async editMessage(messageId: number, body: string): Promise<CommunityMessage> {
    const response = await api.patch<CommunityMessage>(`/api/community/messages/${messageId}`, {
      body,
    });
    return response.data;
  },

  async deleteMessage(messageId: number): Promise<void> {
    await api.delete(`/api/community/messages/${messageId}`);
  },

  async markRead(conversationId: number): Promise<void> {
    await api.post(`/api/community/conversations/${conversationId}/read`);
  },

  async setConversationMuted(conversationId: number, muted: boolean): Promise<void> {
    await api.put(`/api/community/conversations/${conversationId}/mute`, null, {
      params: { muted },
    });
  },

  // ------------------------------------------------------------- reactions
  async getMessageReactions(messageId: number): Promise<MessageReactionSummary> {
    const response = await api.get<MessageReactionSummary>(
      `/api/community/messages/${messageId}/reactions`,
    );
    return response.data;
  },

  async addMessageReaction(messageId: number, reaction: string): Promise<void> {
    await api.post(`/api/community/messages/${messageId}/reactions`, { reaction });
  },

  async removeMessageReaction(messageId: number, reaction: string): Promise<void> {
    await api.delete(`/api/community/messages/${messageId}/reactions`, {
      data: { reaction },
    });
  },

  // ----------------------------------------------------------------- blocks
  async blockMember(userId: number): Promise<{ status: string }> {
    const response = await api.post<{ status: string }>("/api/community/members/block", {
      user_id: userId,
    });
    return response.data;
  },

  async unblockMember(userId: number): Promise<{ user_id: number; status: string }> {
    const response = await api.delete<{ user_id: number; status: string }>(
      `/api/community/members/block/${userId}`,
    );
    return response.data;
  },

  async getBlocks(): Promise<{ blocked: BlockEntry[]; blocked_me: BlockEntry[] }> {
    const response = await api.get<{ blocked: BlockEntry[]; blocked_me: BlockEntry[] }>(
      "/api/community/members/blocks",
    );
    return response.data;
  },

  // ----------------------------------------------------- message reporting
  async reportMessage(
    messageId: number,
    payload: { category: ReportCategory; reason: string; description?: string },
  ): Promise<ReportResult> {
    const response = await api.post<ReportResult>(
      `/api/community/messages/${messageId}/report`,
      {
        category: payload.category,
        reason: payload.reason,
        description: payload.description ?? "",
      },
    );
    return response.data;
  },

  /**
   * Catalogue/community reporting. The moderation scope is derived server-side
   * from the reported resource, so no scope identifier is ever sent from here.
   */
  async submitReport(payload: {
    resourceType: ReportableResourceType;
    resourceId: number;
    category: ReportCategory;
    reason: string;
    description?: string;
  }): Promise<ReportResult> {
    const response = await api.post<ReportResult>("/api/reports/", {
      resource_type: payload.resourceType,
      resource_id: payload.resourceId,
      category: payload.category,
      reason: payload.reason,
      description: payload.description ?? "",
    });
    return response.data;
  },

  // --------------------------------------------------------------- messages
  async getNotificationPreferences(): Promise<NotificationPreferences> {
    const response = await api.get<NotificationPreferences>(
      "/api/community/notification-preferences",
    );
    return response.data;
  },

  async updateNotificationPreferences(
    preferences: NotificationPreferences,
  ): Promise<NotificationPreferences> {
    const response = await api.put<NotificationPreferences>(
      "/api/community/notification-preferences",
      preferences,
    );
    return response.data;
  },

  // ------------------------------------------------------------------ audit
  async getAuditLog(limit?: number): Promise<CommunityAuditRecord[]> {
    const response = await api.get<CommunityAuditRecord[]>("/api/community/audit", {
      params: limit ? { limit } : undefined,
    });
    return response.data;
  },
};