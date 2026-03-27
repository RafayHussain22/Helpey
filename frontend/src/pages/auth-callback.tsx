import { useEffect } from 'react';
import { useNavigate } from 'react-router';
import { apiFetch } from '@/lib/api';
import { useAuthStore } from '@/stores/auth-store';

export default function AuthCallbackPage() {
  const navigate = useNavigate();
  const setUser = useAuthStore((s) => s.setUser);

  useEffect(() => {
    apiFetch<{ id: string; email: string; name: string; picture: string; google_drive_connected: boolean; initial_sync_done: boolean }>(
      '/auth/me',
    )
      .then((user) => {
        setUser(user);
        navigate('/', { replace: true });
      })
      .catch(() => {
        navigate('/login', { replace: true });
      });
  }, [navigate, setUser]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <p className="text-gray-500">Signing you in...</p>
    </div>
  );
}
