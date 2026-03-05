import { createBrowserRouter } from 'react-router';
import LoginPage from '@/pages/login';
import ChatPage from '@/pages/chat';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <ChatPage />,
  },
  {
    path: '/login',
    element: <LoginPage />,
  },
]);
