import { useEffect } from 'react';
import { apiFetch } from '@/lib/api';
import { streamMessage } from '@/lib/sse';
import { useChatStore, type Chat, type ChatMessage } from '@/stores/chat-store';
import ChatSidebar from '@/components/chat-sidebar';
import ChatThread from '@/components/chat-thread';
import ChatInput from '@/components/chat-input';

export default function ChatPage() {
  const {
    activeChatId,
    isStreaming,
    setActiveChatId,
    setMessages,
    addMessage,
    addChat,
    setStreaming,
    appendStreamingContent,
    setStreamingSources,
    finalizeStreaming,
    setError,
    chats,
  } = useChatStore();

  // Load messages when active chat changes
  useEffect(() => {
    if (!activeChatId) {
      setMessages([]);
      return;
    }

    apiFetch<{ messages: ChatMessage[] }>(`/chats/${activeChatId}`)
      .then((data) => setMessages(data.messages))
      .catch(console.error);
  }, [activeChatId, setMessages]);

  const handleSend = async (content: string) => {
    let chatId = activeChatId;

    // Create a new chat if none selected
    if (!chatId) {
      const chat = await apiFetch<Chat>('/chats', {
        method: 'POST',
        body: JSON.stringify({ title: content.slice(0, 80) }),
      });
      addChat(chat);
      setActiveChatId(chat.id);
      chatId = chat.id;
    }

    // Add user message to UI immediately
    const tempId = `temp_${Date.now()}`;
    addMessage({
      id: tempId,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    });

    // Stream assistant response
    setStreaming(true);

    try {
      await streamMessage(chatId, content, {
        onSources: (sources) => setStreamingSources(sources),
        onText: (chunk) => appendStreamingContent(chunk),
        onDone: (messageId) => {
          finalizeStreaming(messageId);
          // Update chat title in sidebar
          const chat = chats.find((c) => c.id === chatId);
          if (chat && chat.title === 'New Chat') {
            chat.title = content.slice(0, 80);
          }
        },
        onError: (error) => {
          console.error('Stream error:', error);
          setError(error);
        },
      });
    } catch (err) {
      console.error('Failed to send message:', err);
      setError(err instanceof Error ? err.message : 'Failed to send message');
    }
  };

  return (
    <div className="flex h-screen bg-background dark:bg-dark-bg">
      <ChatSidebar />
      <div className="flex flex-1 flex-col">
        <ChatThread />
        <ChatInput onSend={handleSend} disabled={isStreaming} />
      </div>
    </div>
  );
}
