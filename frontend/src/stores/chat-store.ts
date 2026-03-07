import { create } from 'zustand';
import type { Source } from '@/lib/sse';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[] | null;
  created_at: string;
}

export interface Chat {
  id: string;
  title: string;
  created_at: string;
}

interface ChatState {
  chats: Chat[];
  activeChatId: string | null;
  messages: ChatMessage[];
  isStreaming: boolean;
  streamingContent: string;
  streamingSources: Source[];
  error: string | null;
  setChats: (chats: Chat[]) => void;
  addChat: (chat: Chat) => void;
  removeChat: (id: string) => void;
  setActiveChatId: (id: string | null) => void;
  setMessages: (messages: ChatMessage[]) => void;
  addMessage: (message: ChatMessage) => void;
  setStreaming: (streaming: boolean) => void;
  appendStreamingContent: (chunk: string) => void;
  setStreamingSources: (sources: Source[]) => void;
  finalizeStreaming: (messageId: string) => void;
  setError: (error: string | null) => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  chats: [],
  activeChatId: null,
  messages: [],
  isStreaming: false,
  streamingContent: '',
  streamingSources: [],
  error: null,
  setChats: (chats) => set({ chats }),
  addChat: (chat) => set((s) => ({ chats: [chat, ...s.chats] })),
  removeChat: (id) =>
    set((s) => ({
      chats: s.chats.filter((c) => c.id !== id),
      activeChatId: s.activeChatId === id ? null : s.activeChatId,
      messages: s.activeChatId === id ? [] : s.messages,
    })),
  setActiveChatId: (id) => set({ activeChatId: id }),
  setMessages: (messages) => set({ messages, error: null }),
  addMessage: (message) => set((s) => ({ messages: [...s.messages, message] })),
  setStreaming: (isStreaming) =>
    set(isStreaming ? { isStreaming, streamingContent: '', streamingSources: [], error: null } : { isStreaming }),
  appendStreamingContent: (chunk) =>
    set((s) => ({ streamingContent: s.streamingContent + chunk })),
  setStreamingSources: (streamingSources) => set({ streamingSources }),
  finalizeStreaming: (messageId) => {
    const { streamingContent, streamingSources } = get();
    set((s) => ({
      messages: [
        ...s.messages,
        {
          id: messageId,
          role: 'assistant' as const,
          content: streamingContent,
          sources: streamingSources.length > 0 ? streamingSources : null,
          created_at: new Date().toISOString(),
        },
      ],
      isStreaming: false,
      streamingContent: '',
      streamingSources: [],
    }));
  },
  setError: (error) => set({ error, isStreaming: false }),
}));
