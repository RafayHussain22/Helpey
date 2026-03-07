import { useState, useRef } from 'react';

interface Props {
  onSend: (content: string) => void;
  disabled: boolean;
}

export default function ChatInput({ onSend, disabled }: Props) {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = Math.min(el.scrollHeight, 160) + 'px';
    }
  };

  return (
    <div className="border-t border-gray-200 bg-white px-4 py-3 dark:border-dark-border dark:bg-dark-surface">
      <div className="mx-auto flex max-w-3xl items-end gap-2">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          placeholder="Ask about your documents..."
          rows={1}
          disabled={disabled}
          className="flex-1 resize-none rounded-xl border border-gray-300 bg-gray-50 px-4 py-2.5 text-sm text-gray-900 outline-none placeholder:text-gray-400 focus:border-primary focus:ring-1 focus:ring-primary disabled:opacity-50 dark:border-dark-border dark:bg-dark-bg dark:text-gray-100 dark:placeholder:text-gray-500"
        />
        <button
          onClick={handleSubmit}
          disabled={disabled || !value.trim()}
          className="shrink-0 rounded-xl bg-primary p-2.5 text-white transition-colors hover:bg-primary-dark disabled:opacity-40"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" />
          </svg>
        </button>
      </div>
    </div>
  );
}
