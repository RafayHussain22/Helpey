import { useCallback, useEffect, useRef, useState } from 'react';
import { apiFetch } from '@/lib/api';

interface SyncStatus {
  initial_sync_done: boolean;
  last_sync_at: string | null;
  total: number;
  pending: number;
  syncing: number;
  downloaded: number;
  processing: number;
  processed: number;
  failed: number;
  is_syncing: boolean;
}

export default function SyncDashboard() {
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await apiFetch<SyncStatus>('/documents/sync/status');
      setStatus(data);
      return data;
    } catch (e) {
      console.error('Failed to fetch sync status:', e);
      return null;
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // Polling: always poll while is_syncing is true (includes !initial_sync_done)
  useEffect(() => {
    if (status === null) return; // Haven't fetched yet

    if (status.is_syncing) {
      if (!intervalRef.current) {
        intervalRef.current = setInterval(fetchStatus, 2000);
      }
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [status?.is_syncing, fetchStatus]);

  const handleRetryFailed = async () => {
    setRetrying(true);
    try {
      await apiFetch('/documents/reprocess-failed', { method: 'POST' });
      await fetchStatus();
    } catch (e) {
      console.error('Failed to retry failed files:', e);
    } finally {
      setRetrying(false);
    }
  };

  const handleResync = async () => {
    setTriggering(true);
    try {
      await apiFetch('/documents/sync', { method: 'POST' });
      await fetchStatus();
    } catch (e) {
      console.error('Failed to trigger sync:', e);
    } finally {
      setTriggering(false);
    }
  };

  if (!status) {
    return (
      <div className="px-3 py-2">
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <Spinner />
          Loading sync status...
        </div>
      </div>
    );
  }

  const { initial_sync_done, is_syncing, total, processed, failed, syncing, downloaded, processing, pending } = status;
  const inProgress = pending + syncing + downloaded + processing;

  return (
    <div className="px-3 py-2 space-y-2">
      {/* Progress bar */}
      {(total > 0 || is_syncing) && (
        <div>
          <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 mb-1">
            <span className="font-medium">Drive Files</span>
            {total > 0 ? (
              <span className="font-mono">{processed + failed}/{total}</span>
            ) : (
              <span>Scanning...</span>
            )}
          </div>
          <div className="h-1.5 w-full rounded-full bg-gray-200 dark:bg-dark-border overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                is_syncing ? 'bg-primary/70 animate-pulse' : 'bg-primary'
              }`}
              style={{ width: total > 0 ? `${((processed + failed) / total) * 100}%` : '0%' }}
            />
          </div>
        </div>
      )}

      {/* Detailed status breakdown while syncing */}
      {is_syncing && (
        <div className="space-y-1">
          {!initial_sync_done && total === 0 && (
            <StatusRow icon={<Spinner />} label="Scanning Google Drive..." />
          )}
          {syncing > 0 && (
            <StatusRow
              icon={<DownloadIcon />}
              label={`${syncing} downloading`}
            />
          )}
          {(downloaded + processing) > 0 && (
            <StatusRow
              icon={<Spinner />}
              label={`${downloaded + processing} processing`}
            />
          )}
          {processed > 0 && (
            <StatusRow
              icon={<CheckIcon />}
              label={`${processed} indexed`}
              className="text-green-600 dark:text-green-400"
            />
          )}
          {failed > 0 && (
            <StatusRow
              icon={<WarningIcon />}
              label={`${failed} failed`}
              className="text-red-500"
            />
          )}
        </div>
      )}

      {/* Static summary when done */}
      {!is_syncing && (
        <div className="space-y-1">
          <StatusRow
            icon={<CheckIcon />}
            label={`${processed} file${processed !== 1 ? 's' : ''} indexed`}
            className="text-green-600 dark:text-green-400"
          />
          {failed > 0 && (
            <div className="flex items-center justify-between">
              <StatusRow
                icon={<WarningIcon />}
                label={`${failed} failed`}
                className="text-red-500"
              />
              <button
                onClick={handleRetryFailed}
                disabled={retrying}
                className="text-xs font-medium text-primary-dark hover:underline disabled:opacity-50 dark:text-primary-light"
              >
                {retrying ? 'Retrying...' : 'Retry all'}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Re-sync button */}
      {!is_syncing && initial_sync_done && (
        <button
          onClick={handleResync}
          disabled={triggering}
          className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-primary/10 px-2.5 py-1.5 text-xs font-medium text-primary-dark hover:bg-primary/20 transition-colors disabled:opacity-50 dark:bg-primary/20 dark:text-primary-light dark:hover:bg-primary/30"
        >
          <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          {triggering ? 'Starting...' : 'Re-sync Drive'}
        </button>
      )}
    </div>
  );
}

function StatusRow({ icon, label, className = 'text-gray-500 dark:text-gray-400' }: {
  icon: React.ReactNode;
  label: string;
  className?: string;
}) {
  return (
    <div className={`flex items-center gap-1.5 text-xs ${className}`}>
      {icon}
      <span>{label}</span>
    </div>
  );
}

function Spinner() {
  return (
    <svg className="h-3.5 w-3.5 shrink-0 animate-spin text-primary" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg className="h-3.5 w-3.5 shrink-0 text-blue-500 animate-bounce" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
    </svg>
  );
}

function WarningIcon() {
  return (
    <svg className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
    </svg>
  );
}
