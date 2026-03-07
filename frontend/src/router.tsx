import { createBrowserRouter, Navigate, Outlet } from 'react-router';
import LoginPage from '@/pages/login';
import ChatPage from '@/pages/chat';
import AuthCallbackPage from '@/pages/auth-callback';
import { useAuthStore } from '@/stores/auth-store';

function ProtectedRoute() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isLoading = useAuthStore((s) => s.isLoading);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}

function PublicOnlyRoute() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isLoading = useAuthStore((s) => s.isLoading);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}

export const router = createBrowserRouter([
  {
    element: <ProtectedRoute />,
    children: [
      { path: '/', element: <ChatPage /> },
    ],
  },
  {
    element: <PublicOnlyRoute />,
    children: [
      { path: '/login', element: <LoginPage /> },
    ],
  },
  {
    path: '/auth/callback',
    element: <AuthCallbackPage />,
  },
]);
