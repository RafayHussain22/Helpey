import { useAuthStore } from '@/stores/auth-store';

export default function DriveConnectBanner() {
  const user = useAuthStore((s) => s.user);

  if (!user || user.google_drive_connected) return null;

  return (
    <div className="flex items-center justify-between gap-4 border-b border-amber-200 bg-amber-50 px-4 py-3 dark:border-amber-800 dark:bg-amber-950">
      <p className="text-sm text-amber-800 dark:text-amber-200">
        Connect your Google Drive to start chatting with your files.
      </p>
      <a
        href="/api/auth/google/connect"
        className="shrink-0 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-dark transition-colors"
      >
        Connect Google Drive
      </a>
    </div>
  );
}
