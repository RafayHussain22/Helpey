import { useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';
import { useAuthStore } from '@/stores/auth-store';
import { useChatStore, type Chat } from '@/stores/chat-store';
import SyncDashboard from '@/components/sync-dashboard';

function useTheme() {
  const [dark, setDark] = useState(() => {
    if (typeof window === 'undefined') return false;
    return localStorage.getItem('theme') === 'dark';
  });

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
    localStorage.setItem('theme', dark ? 'dark' : 'light');
  }, [dark]);

  return [dark, () => setDark((d) => !d)] as const;
}

export default function ChatSidebar() {
  const user = useAuthStore((s) => s.user);
  const { chats, activeChatId, setChats, addChat, removeChat, setActiveChatId, setMessages } =
    useChatStore();
  const [dark, toggleTheme] = useTheme();

  useEffect(() => {
    apiFetch<Chat[]>('/chats').then(setChats).catch(console.error);
  }, [setChats]);

  const handleNewChat = async () => {
    const chat = await apiFetch<Chat>('/chats', {
      method: 'POST',
      body: JSON.stringify({ title: 'New Chat' }),
    });
    addChat(chat);
    setActiveChatId(chat.id);
    setMessages([]);
  };

  const handleDelete = async (e: React.MouseEvent, chatId: string) => {
    e.stopPropagation();
    await apiFetch(`/chats/${chatId}`, { method: 'DELETE' });
    removeChat(chatId);
  };

  const handleLogout = async () => {
    await apiFetch('/auth/logout', { method: 'POST' });
    window.location.href = '/login';
  };

  return (
    <div className="flex h-full w-64 flex-col border-r border-gray-200 bg-white dark:border-dark-border dark:bg-dark-surface">
      {/* Top buttons */}
      <div className="p-3">
        <button
          onClick={handleNewChat}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors dark:border-dark-border dark:text-gray-300 dark:hover:bg-dark-bg"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New Chat
        </button>
      </div>

      {/* Sync dashboard */}
      {user?.google_drive_connected && (
        <div className="border-b border-gray-200 dark:border-dark-border">
          <SyncDashboard />
        </div>
      )}

      {/* Chat list */}
      <div className="flex-1 overflow-y-auto px-2">
        {chats.map((chat) => (
          <button
            key={chat.id}
            onClick={() => setActiveChatId(chat.id)}
            className={`group mb-0.5 flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm transition-colors ${
              activeChatId === chat.id
                ? 'bg-primary/10 text-primary-dark dark:bg-primary/20 dark:text-primary-light'
                : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-dark-bg'
            }`}
          >
            <span className="truncate">{chat.title}</span>
            <button
              onClick={(e) => handleDelete(e, chat.id)}
              className="ml-1 hidden shrink-0 rounded p-0.5 text-gray-400 hover:text-red-500 group-hover:block"
            >
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </button>
        ))}
      </div>

      {/* User section */}
      <div className="border-t border-gray-200 p-3 dark:border-dark-border">
        <div className="flex items-center gap-2">
          {user?.picture && (
            <img src={user.picture} alt="" className="h-7 w-7 rounded-full" />
          )}
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-gray-900 dark:text-gray-100">{user?.name}</p>
          </div>
          <button
            onClick={toggleTheme}
            className="shrink-0 rounded p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
            title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {dark ? (
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
            ) : (
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
              </svg>
            )}
          </button>
          <button
            onClick={handleLogout}
            className="shrink-0 rounded p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
            title="Sign out"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
