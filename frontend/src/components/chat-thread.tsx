import { useEffect, useRef } from 'react';
import { useChatStore } from '@/stores/chat-store';
import MessageBubble, { StreamingBubble } from '@/components/message-bubble';

export default function ChatThread() {
  const { messages, isStreaming, streamingContent, streamingSources, error } = useChatStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent, error]);

  if (messages.length === 0 && !isStreaming && !error) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <div className="text-center">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Helpey</h2>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Ask questions about your Google Drive documents.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6">
      <div className="mx-auto max-w-3xl space-y-4">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {isStreaming && (
          <StreamingBubble content={streamingContent} sources={streamingSources} />
        )}
        {error && (
          <div className="flex justify-start">
            <div className="max-w-[75%] rounded-2xl bg-red-50 px-4 py-2.5 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
              <p className="font-medium">Something went wrong</p>
              <p className="mt-1 text-red-600 dark:text-red-400">{error.length > 200 ? error.slice(0, 200) + '...' : error}</p>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
