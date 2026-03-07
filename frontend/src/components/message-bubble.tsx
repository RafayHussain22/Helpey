import type { ChatMessage } from '@/stores/chat-store';
import type { Source } from '@/lib/sse';

interface Props {
  message: ChatMessage;
}

export default function MessageBubble({ message }: Props) {
  return (
    <div
      className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
    >
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-2.5 ${
          message.role === 'user'
            ? 'bg-primary text-white'
            : 'bg-gray-100 text-gray-900 dark:bg-dark-surface dark:text-gray-100'
        }`}
      >
        <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</p>
        {message.sources && message.sources.length > 0 && (
          <SourcesList sources={message.sources} />
        )}
      </div>
    </div>
  );
}

export function StreamingBubble({ content, sources }: { content: string; sources: Source[] }) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[75%] rounded-2xl bg-gray-100 px-4 py-2.5 text-gray-900 dark:bg-dark-surface dark:text-gray-100">
        <p className="whitespace-pre-wrap text-sm leading-relaxed">
          {content || (
            <span className="inline-flex gap-1">
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400" style={{ animationDelay: '0ms' }} />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400" style={{ animationDelay: '150ms' }} />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400" style={{ animationDelay: '300ms' }} />
            </span>
          )}
        </p>
        {sources.length > 0 && <SourcesList sources={sources} />}
      </div>
    </div>
  );
}

function SourcesList({ sources }: { sources: Source[] }) {
  // Dedupe by filename
  const unique = sources.filter(
    (s, i, arr) => arr.findIndex((x) => x.filename === s.filename) === i,
  );

  return (
    <div className="mt-2 border-t border-gray-200 pt-2 dark:border-dark-border">
      <p className="mb-1 text-xs font-medium text-gray-500 dark:text-gray-400">Sources:</p>
      <div className="flex flex-wrap gap-1">
        {unique.map((s, i) => (
          <span
            key={i}
            className="inline-block rounded bg-gray-200 px-1.5 py-0.5 text-xs text-gray-600 dark:bg-dark-bg dark:text-gray-400"
          >
            {s.filename}
          </span>
        ))}
      </div>
    </div>
  );
}
