import { useCallback, useEffect, useRef, useState } from 'react';
import { apiFetch } from '@/lib/api';

interface DriveFile {
  id: string;
  name: string;
  mimeType: string;
  size?: string;
  modifiedTime: string;
  synced: boolean;
  sync_status?: string;
}

interface DriveFilesResponse {
  files: DriveFile[];
  nextPageToken?: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
}

const MIME_ICONS: Record<string, string> = {
  'application/pdf': '📄',
  'application/vnd.google-apps.document': '📝',
  'application/vnd.google-apps.spreadsheet': '📊',
  'application/vnd.google-apps.presentation': '📽️',
  'text/plain': '📃',
  'text/csv': '📊',
  'image/png': '🖼️',
  'image/jpeg': '🖼️',
};

function formatSize(bytes?: string) {
  if (!bytes) return '—';
  const n = parseInt(bytes, 10);
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

export default function DrivePicker({ open, onClose }: Props) {
  const [files, setFiles] = useState<DriveFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [syncing, setSyncing] = useState(false);
  const [nextPageToken, setNextPageToken] = useState<string | undefined>();
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const searchTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const searchInputRef = useRef<HTMLInputElement>(null);

  const loadFiles = useCallback(async (query: string, pageToken?: string) => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (pageToken) params.set('page_token', pageToken);
      if (query) params.set('search', query);
      const qs = params.toString();
      const url = `/documents/drive/files${qs ? `?${qs}` : ''}`;
      const data = await apiFetch<DriveFilesResponse>(url);
      setFiles((prev) => (pageToken ? [...prev, ...data.files] : data.files));
      setNextPageToken(data.nextPageToken);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load files');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      setFiles([]);
      setSelected(new Set());
      setNextPageToken(undefined);
      setSearch('');
      loadFiles('');
      // Focus search on open
      setTimeout(() => searchInputRef.current?.focus(), 100);
    }
  }, [open, loadFiles]);

  // Debounced search
  const handleSearchChange = (value: string) => {
    setSearch(value);
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    searchTimerRef.current = setTimeout(() => {
      setFiles([]);
      setNextPageToken(undefined);
      loadFiles(value);
    }, 400);
  };

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    const unsynced = files.filter((f) => !f.synced).map((f) => f.id);
    setSelected((prev) =>
      prev.size === unsynced.length ? new Set() : new Set(unsynced),
    );
  };

  const handleSync = async () => {
    if (selected.size === 0) return;
    setSyncing(true);
    try {
      await apiFetch('/documents/sync', {
        method: 'POST',
        body: JSON.stringify({ file_ids: [...selected] }),
      });
      setFiles((prev) =>
        prev.map((f) =>
          selected.has(f.id) ? { ...f, synced: true, sync_status: 'syncing' } : f,
        ),
      );
      setSelected(new Set());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sync failed');
    } finally {
      setSyncing(false);
    }
  };

  if (!open) return null;

  const unsyncedCount = files.filter((f) => !f.synced).length;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="flex max-h-[80vh] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-xl dark:bg-dark-surface">
        {/* Header */}
        <div className="border-b border-gray-200 px-5 py-4 dark:border-dark-border">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Google Drive Files</h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Search and select files to use as your knowledge base
              </p>
            </div>
            <button
              onClick={onClose}
              className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Search box */}
          <div className="relative mt-3">
            <svg
              className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              ref={searchInputRef}
              type="text"
              value={search}
              onChange={(e) => handleSearchChange(e.target.value)}
              placeholder="Search your Drive files..."
              className="w-full rounded-lg border border-gray-300 bg-gray-50 py-2 pl-10 pr-4 text-sm text-gray-900 outline-none placeholder:text-gray-400 focus:border-primary focus:ring-1 focus:ring-primary dark:border-dark-border dark:bg-dark-bg dark:text-gray-100 dark:placeholder:text-gray-500"
            />
            {search && (
              <button
                onClick={() => handleSearchChange('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
        </div>

        {/* File list */}
        <div className="flex-1 overflow-y-auto px-5 py-3">
          {error && (
            <div className="mb-3 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-600">
              {error}
            </div>
          )}

          {loading && files.length === 0 ? (
            <div className="flex items-center justify-center py-12">
              <p className="text-sm text-gray-500">
                {search ? `Searching for "${search}"...` : 'Loading Drive files...'}
              </p>
            </div>
          ) : files.length === 0 ? (
            <div className="flex items-center justify-center py-12">
              <p className="text-sm text-gray-500">
                {search
                  ? `No files found matching "${search}"`
                  : 'No supported files found in your Drive'}
              </p>
            </div>
          ) : (
            <>
              {unsyncedCount > 0 && (
                <button
                  onClick={selectAll}
                  className="mb-2 text-xs font-medium text-primary hover:text-primary-dark"
                >
                  {selected.size === unsyncedCount ? 'Deselect all' : `Select all (${unsyncedCount})`}
                </button>
              )}
              <div className="space-y-1">
                {files.map((file) => (
                  <label
                    key={file.id}
                    className={`flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 transition-colors ${
                      file.synced
                        ? 'cursor-default opacity-60'
                        : selected.has(file.id)
                          ? 'bg-primary/5 ring-1 ring-primary/30'
                          : 'hover:bg-gray-50'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selected.has(file.id) || file.synced}
                      disabled={file.synced}
                      onChange={() => toggleSelect(file.id)}
                      className="h-4 w-4 rounded border-gray-300 text-primary accent-primary"
                    />
                    <span className="text-lg leading-none">
                      {MIME_ICONS[file.mimeType] ?? '📄'}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-gray-900 dark:text-gray-100">
                        {file.name}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {formatSize(file.size)} · {formatDate(file.modifiedTime)}
                      </p>
                    </div>
                    {file.synced && (
                      <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
                        file.sync_status === 'processed'
                          ? 'bg-green-100 text-green-700'
                          : file.sync_status === 'failed'
                            ? 'bg-red-100 text-red-700'
                            : 'bg-blue-100 text-blue-700'
                      }`}>
                        {file.sync_status ?? 'synced'}
                      </span>
                    )}
                  </label>
                ))}
              </div>
              {nextPageToken && (
                <button
                  onClick={() => loadFiles(search, nextPageToken)}
                  disabled={loading}
                  className="mt-3 w-full rounded-lg border border-gray-200 py-2 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-50"
                >
                  {loading ? 'Loading...' : 'Load more'}
                </button>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-gray-200 px-5 py-3 dark:border-dark-border">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {selected.size > 0 ? `${selected.size} file${selected.size > 1 ? 's' : ''} selected` : 'No files selected'}
          </p>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="rounded-lg px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-dark-bg"
            >
              Cancel
            </button>
            <button
              onClick={handleSync}
              disabled={selected.size === 0 || syncing}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-40"
            >
              {syncing ? 'Syncing...' : `Sync ${selected.size > 0 ? selected.size : ''} file${selected.size !== 1 ? 's' : ''}`}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
