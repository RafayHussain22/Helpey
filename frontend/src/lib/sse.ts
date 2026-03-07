const API_BASE = '/api';

export interface SSECallbacks {
  onSources?: (sources: Source[]) => void;
  onText?: (chunk: string) => void;
  onDone?: (messageId: string) => void;
  onError?: (error: string) => void;
}

export interface Source {
  document_id: string;
  filename: string;
  excerpt: string;
}

export async function streamMessage(
  chatId: string,
  content: string,
  callbacks: SSECallbacks,
): Promise<void> {
  const res = await fetch(`${API_BASE}/chats/${chatId}/messages`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? res.statusText);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error('No response body');

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const json = line.slice(6);
      try {
        const event = JSON.parse(json);
        switch (event.type) {
          case 'sources':
            callbacks.onSources?.(event.sources);
            break;
          case 'text':
            callbacks.onText?.(event.content);
            break;
          case 'done':
            callbacks.onDone?.(event.message_id);
            break;
          case 'error':
            callbacks.onError?.(event.content);
            break;
        }
      } catch {
        // skip malformed JSON
      }
    }
  }
}
