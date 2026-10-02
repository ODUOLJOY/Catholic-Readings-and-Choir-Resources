import { api } from "@/lib/api";

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
  created_at: string;
};

export type CommunityMember = {
  id: number;
  full_name: string;
  parish_id: number | null;
};

export const communityService = {
  async getConversations(): Promise<ConversationSummary[]> {
    const response = await api.get<ConversationSummary[]>("/api/community/conversations");
    return response.data;
  },

  async getMessages(conversationId: number): Promise<CommunityMessage[]> {
    const response = await api.get<CommunityMessage[]>(
      `/api/community/conversations/${conversationId}/messages`,
    );
    return response.data;
  },

  async sendMessage(conversationId: number, body: string): Promise<CommunityMessage> {
    const response = await api.post<CommunityMessage>(
      `/api/community/conversations/${conversationId}/messages`,
      { body },
    );
    return response.data;
  },

  async markRead(conversationId: number): Promise<void> {
    await api.post(`/api/community/conversations/${conversationId}/read`);
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
};
