import { useEffect } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from 'react-router';
import { queryClient } from '@/lib/query-client';
import { router } from '@/router';
import { useAuthStore } from '@/stores/auth-store';
import { apiFetch } from '@/lib/api';

export default function App() {
  const setUser = useAuthStore((s) => s.setUser);

  useEffect(() => {
    apiFetch<{ id: string; email: string; name: string; picture: string }>(
      '/auth/me',
    )
      .then((user) => setUser(user))
      .catch(() => setUser(null));
  }, [setUser]);

  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}
